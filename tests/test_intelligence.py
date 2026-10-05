import io
from unittest.mock import Mock, patch
import fitz
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from qa.models import Document, Chunk, Obligation, ObligationExtractionRecord, GapFinding, QueryLog, AgentStep
from qa.services.obligations import extract_obligations, review_obligation
from qa.services.gap_analysis import run_gap_analysis
from qa.services.reports import gap_pdf
from qa.services.analytics import summarize
from rag.schemas import Extraction, GapJudgment
from rag.retriever import fuse, search_documents, evidence_dict, expand_structural_context
from rag.vectorstore import rebuild, VectorStore
from rag.agent import gather, needs_agent
from rag.tools import execute
from tests.test_foundation import IsolatedCase


class RetrievalTests(IsolatedCase):
    def test_rrf_combines_ranks_without_mixing_raw_scores(self):
        merged = fuse([(1, .7), (2, .6)], [(2, 12.), (3, 4.)])
        self.assertEqual(merged[0]['chunk_id'], 2)
        self.assertAlmostEqual(merged[0]['score'], 1 / 62 + 1 / 61)

    def test_policy_filter_happens_before_topk(self):
        regulation = self.document('Rule')
        policy = self.document('Policy', document_type='company_policy', regulator='')
        rebuild()
        with patch.object(VectorStore, 'search', return_value=[(regulation.chunks.get().pk, .9), (policy.chunks.get().pk, .8)]):
            result = search_documents('policy', document_ids=[policy.pk], document_type='company_policy', mode='dense', top_k=1)
        self.assertEqual(result[0]['document_id'], policy.pk)

    def test_explicit_document_scope_excludes_better_scoring_other_source(self):
        other = self.document('Other source')
        selected = self.document('Selected source')
        rebuild()
        ranked = [(other.chunks.get().pk, .99), (selected.chunks.get().pk, .8)]
        with patch.object(VectorStore, 'search', return_value=ranked):
            result = search_documents('source', document_ids=[selected.pk], document_type=None,
                                      mode='dense', top_k=5)
        self.assertEqual([row['document_id'] for row in result], [selected.pk])

    def test_empty_explicit_scope_does_not_mean_all_documents(self):
        self.document('Source')
        rebuild()
        self.assertEqual(search_documents('source', document_ids=[], document_type=None), [])

    def test_lexical_hit_can_survive_dense_threshold(self):
        doc = self.document('Key Fact Statement must be disclosed.')
        rebuild()
        with patch.object(VectorStore, 'search', return_value=[]):
            with patch('rag.retriever.lexical_search', return_value=[(doc.chunks.get().pk, 3.)]):
                result = search_documents('Key Fact Statement', mode='hybrid')
        self.assertEqual(result[0]['bm25_score'], 3.)

    def test_reranker_score_is_not_probability(self):
        doc = self.document()
        rebuild()
        with patch.object(VectorStore, 'search', return_value=[(doc.chunks.get().pk, .8)]):
            with patch('rag.retriever.rerank', side_effect=lambda q, cs, k: [dict(cs[0], reranker_score=7.3)]):
                result = search_documents('records', mode='hybrid_rerank')
        self.assertEqual(result[0]['reranker_score'], 7.3)
        self.assertNotIn('probability', result[0])

    def test_list_intro_expands_numbered_children_and_stops_at_next_section(self):
        doc = self.document('5. The following measures shall be adopted.')
        anchor = doc.chunks.get()
        anchor.paragraph_id = '5.'
        anchor.save(update_fields=['paragraph_id'])
        children = []
        for index, paragraph in enumerate(('5.1.', '5.1.1.', '5.2.', '6.'), 1):
            text = f'{paragraph} Clause text'
            children.append(Chunk.objects.create(
                document=doc, chunk_index=index, paragraph_id=paragraph, text=text,
                content_sha256='a' * 64, chunker_version='2', start_page=1, end_page=1,
            ))
        store = Mock(rows=list(doc.chunks.all()))

        result = expand_structural_context([dict(evidence_dict(anchor), score=.8)], store)

        self.assertEqual([item['paragraph_id'] for item in result], ['5.', '5.1.', '5.1.1.', '5.2.'])
        self.assertEqual(result[0]['retrieval_role'], 'ranked')
        self.assertTrue(all(item['retrieval_role'] == 'structural_neighbor' for item in result[1:]))

    @override_settings(RAG_MAX_CONTEXT_CHUNKS=2)
    def test_structural_context_respects_configured_cap(self):
        doc = self.document('3. The following changes apply.')
        anchor = doc.chunks.get()
        anchor.paragraph_id = '3.'
        anchor.save(update_fields=['paragraph_id'])
        for index, paragraph in enumerate(('3.1.', '3.2.'), 1):
            Chunk.objects.create(document=doc, chunk_index=index, paragraph_id=paragraph,
                text=f'{paragraph} Change', content_sha256='b' * 64, chunker_version='2')

        result = expand_structural_context([evidence_dict(anchor)], Mock(rows=list(doc.chunks.all())))

        self.assertEqual(len(result), 2)


class AgentTests(IsolatedCase):
    def test_zero_total_budget_does_not_start_worker(self):
        from rag.agent import bounded_call
        with patch('rag.agent.multiprocessing.get_context') as context:
            with self.assertRaises(TimeoutError):
                bounded_call('plan', {}, 0)
        context.assert_not_called()

    def test_multistep_trace(self):
        doc = self.document()
        user = User.objects.create_user('agent-user')
        plan = {'plan': {'summary': 'Search for records.', 'sub_questions': ['Records?'],
                        'steps': [{'tool': 'search_documents', 'arguments': {'query': 'records'}}]}, 'metadata': {}}
        with patch('rag.agent.bounded_call', side_effect=[plan, [evidence_dict(doc.chunks.get())]]):
            run, chunks = gather('Compare records requirements', user)
        self.assertEqual(run.step_count, 1)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(run.steps.count(), 2)

    def test_timeout_abstains_and_records_error(self):
        self.document()
        with patch('rag.agent.bounded_call', side_effect=TimeoutError):
            run, chunks = gather('Compare rules')
        self.assertEqual(run.status, 'abstained')
        self.assertEqual(chunks, [])

    def test_selected_document_scope_rejects_plan_for_other_source(self):
        selected = self.document('Selected')
        other = self.document('Other')
        plan = {'plan': {'summary': 'Search other.', 'sub_questions': ['Other?'],
                        'steps': [{'tool': 'search_documents',
                                   'arguments': {'query': 'other', 'document_ids': [other.pk]}}]}}
        with patch('rag.agent.bounded_call', return_value=plan):
            run, chunks = gather('Compare evidence', document_ids=[selected.pk])
        self.assertEqual(run.status, 'abstained')
        self.assertEqual(chunks, [])
        self.assertEqual(run.error, 'ValueError')

    def test_typed_chunk_tool_cannot_read_outside_selected_scope(self):
        selected = self.document('Selected')
        other = self.document('Other')
        with self.assertRaisesMessage(ValueError, 'outside the selected scope'):
            execute('get_chunks', {'chunk_ids': [other.chunks.get().pk]}, Mock(), [selected.pk])

    def test_unknown_tool_plan_is_rejected(self):
        self.document()
        plan = {'plan': {'summary': '', 'sub_questions': ['?'],
                        'steps': [{'tool': 'execute_code', 'arguments': {'code': 'bad'}}]}}
        with patch('rag.agent.bounded_call', return_value=plan):
            run, chunks = gather('Compare rules')
        self.assertEqual(run.status, 'abstained')
        self.assertEqual(run.step_count, 0)

    def test_configured_step_cap_enforced(self):
        self.document()
        steps = [{'tool': 'search_documents', 'arguments': {'query': 'records'}}] * 3
        plan = {'plan': {'summary': '', 'sub_questions': ['?'], 'steps': steps}}
        with override_settings(RAG_MAX_AGENT_STEPS=2):
            with patch('rag.agent.bounded_call', return_value=plan):
                run, _ = gather('Compare rules')
        self.assertEqual(run.step_count, 0)
        self.assertEqual(run.status, 'abstained')

    def test_changes_need_real_versions(self):
        self.document()
        with patch('rag.agent.bounded_call') as worker:
            run, _ = gather('What changed from the previous version?')
        worker.assert_not_called()
        self.assertEqual(run.status, 'abstained')


class ObligationTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.doc = self.document('Firms must keep records for five years.', source_category='circular')
        self.chunk = self.doc.chunks.get()
        self.reviewer = User.objects.create_user('reviewer')
        rebuild()

    def candidate(self):
        return Extraction(obligations=[dict(obligation_text='Firms must keep records for five years.',
            obligated_party='Firms', condition='', deadline_or_trigger='five years',
            source_quote=self.chunk.text, confidence='high')])

    def test_idempotent_extraction_and_review_gate(self):
        with patch('qa.services.obligations.structured_call', return_value=(self.candidate(), {'model': 'test'})):
            with patch('qa.services.obligations.check_obligation', return_value=(True, 'entailed', 'Supported')):
                extract_obligations(self.doc.pk)
                extract_obligations(self.doc.pk)
        self.assertEqual(Obligation.objects.count(), 1)
        self.assertFalse(Obligation.objects.get().is_confirmed)

    def test_zero_obligations_is_valid_and_resumable(self):
        with patch('qa.services.obligations.structured_call', return_value=(Extraction(obligations=[]), {'model': 'test'})):
            first, second = extract_obligations(self.doc.pk), extract_obligations(self.doc.pk)
        self.assertEqual(first['processed'], 1)
        self.assertEqual(second['processed'], 0)

    def test_consultation_cannot_be_treated_as_binding(self):
        self.doc.source_category = 'consultation_paper'
        self.doc.save()
        with self.assertRaisesMessage(ValueError, 'binding'):
            extract_obligations(self.doc.pk)

    def test_unverified_quote_never_entailed(self):
        from qa.services.obligations import check_obligation
        quoted, status, _ = check_obligation('Invented duty', 'This quote is absent', self.chunk)
        self.assertFalse(quoted)
        self.assertEqual(status, 'not_entailed')

    def test_reviewer_identity_saved(self):
        item = Obligation.objects.create(source_document=self.doc, source_chunk=self.chunk,
            source_content_sha256=self.chunk.content_sha256, source_paragraph_id=self.chunk.paragraph_id,
            source_quote=self.chunk.text, obligation_text=self.chunk.text)
        with patch('qa.services.obligations.check_obligation', return_value=(True, 'entailed', 'Supported')):
            review_obligation(item, self.reviewer, 'confirm')
        item.refresh_from_db()
        self.assertEqual(item.reviewer, self.reviewer)
        self.assertEqual(item.review_status, 'confirmed')


class GapTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.regulation = self.document('Maintain records for five years.', source_category='circular')
        self.policy = self.document('We retain records for five years.', document_type='company_policy', regulator='')
        self.user = User.objects.create_user('reviewer')
        c = self.regulation.chunks.get()
        self.obligation = Obligation.objects.create(source_document=self.regulation, source_chunk=c,
            obligation_text=c.text, source_paragraph_id=c.paragraph_id, source_content_sha256=c.content_sha256,
            source_quote=c.text, quote_verified=True, entailment_status='entailed',
            review_status='confirmed', reviewer=self.user, reviewed_at=timezone.now())
        rebuild()
        self.policy.refresh_from_db()

    def run_with(self, status, chunk_id=None):
        candidate = evidence_dict(self.policy.chunks.get())
        judge = GapJudgment(status=status, policy_chunk_id=chunk_id,
                            explanation='Comparison of the supplied clauses.', confidence='medium')
        with patch('qa.services.gap_analysis.search_documents', return_value=[candidate]):
            with patch('qa.services.gap_analysis.structured_call', return_value=(judge, {'model': 'test'})):
                return run_gap_analysis(self.policy.pk, [self.regulation.pk], self.user)

    def test_each_classification_and_citations(self):
        for status in ('addressed', 'partially_addressed', 'conflicting', 'not_addressed', 'needs_review'):
            with self.subTest(status=status):
                identifier = self.policy.chunks.get().pk if status in ('addressed', 'partially_addressed', 'conflicting') else None
                run = self.run_with(status, identifier)
                finding = run.findings.get()
                self.assertEqual(finding.status, status)
                self.assertEqual(finding.regulatory_evidence['document_id'], self.regulation.pk)
                if identifier:
                    self.assertEqual(finding.policy_evidence['document_id'], self.policy.pk)

    def test_invented_policy_citation_becomes_review_error(self):
        run = self.run_with('addressed', 99999)
        self.assertEqual(run.findings.get().status, 'needs_review')
        self.assertEqual(run.status, 'failed')

    def test_unreviewed_obligation_cannot_enter_analysis(self):
        self.obligation.review_status = 'pending'
        self.obligation.save()
        with self.assertRaisesMessage(ValueError, 'human-confirmed'):
            run_gap_analysis(self.policy.pk, [self.regulation.pk], self.user)

    def test_pdf_opens_and_contains_citations_and_findings(self):
        run = self.run_with('addressed', self.policy.chunks.get().pk)
        pdf = gap_pdf(run)
        with fitz.open(stream=pdf, filetype='pdf') as parsed:
            content = ''.join(page.get_text() for page in parsed)
            self.assertIn('Regulatory source', content)
            self.assertIn('Policy source', content)
            self.assertIn('Maintain records', content)
            self.assertGreaterEqual(len(parsed), 1)

    def test_html_pdf_and_review_require_owner_or_admin(self):
        call_command('bootstrap_roles', stdout=io.StringIO())
        self.user.groups.add(Group.objects.get(name='Contributor'))
        run = self.run_with('addressed', self.policy.chunks.get().pk)
        other = User.objects.create_user('other')
        other.groups.add(Group.objects.get(name='Contributor'))
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('qa:gap_detail', args=[run.pk])).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('qa:gap_detail', args=[run.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('qa:gap_export', args=[run.pk])).status_code, 200)


class GovernanceTests(IsolatedCase):
    def test_human_judge_review_records_provenance_and_agreement(self):
        from qa.models import GoldQuestion, EvalRun, EvalResult
        q = GoldQuestion.objects.create(question='?', expected_answer='Reference')
        run = EvalRun.objects.create(configuration={'mode': 'dense'})
        result = EvalResult.objects.create(eval_run=run, gold_question=q, correctness_label='partial')
        user = User.objects.create_superuser('reviewer', password='test')
        self.client.force_login(user)
        response = self.client.post(reverse('qa:judge_review', args=[result.pk]), {'label': 'partial', 'notes': 'Missing timing condition.'})
        self.assertEqual(response.status_code, 302)
        run.refresh_from_db()
        self.assertEqual(run.configuration['judge_agreement']['exact_agreement'], 1)
        self.assertEqual(run.configuration['human_review_history'][0]['reviewer_id'], user.pk)

    def test_provisional_evaluation_does_not_approve_questions(self):
        from qa.models import GoldQuestion, GoldEvidence
        from qa.services.evaluation import run_evaluation
        doc = self.document()
        q = GoldQuestion.objects.create(question='Records?', expected_answer='Keep records.', split='test')
        GoldEvidence.objects.create(gold_question=q, document=doc, paragraph_id='1')
        rebuild()
        with patch('rag.retriever.search_documents', return_value=[evidence_dict(doc.chunks.get())]):
            run = run_evaluation(allow_unreviewed=True, retrieval_only=True)
        q.refresh_from_db()
        self.assertEqual(run.status, 'provisional')
        self.assertIsNone(q.reviewed_at)
        self.assertIsNone(run.answer_correctness)
        self.assertEqual(run.retrieval_hit_at_k, 1)

    def test_analytics_reconciles_with_logs(self):
        QueryLog.objects.create(question='Loan rule?', not_found=True, response_time_ms=100, review_required=True)
        QueryLog.objects.create(question='Policy?', not_found=False, response_time_ms=300, confidence_band='medium')
        data = summarize()
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['refusal_rate'], .5)
        self.assertEqual(data['median_ms'], 200)
        self.assertEqual(data['open_answers'], 1)

    def test_feature_routes_permissions_and_rendering(self):
        call_command('bootstrap_roles', stdout=io.StringIO())
        viewer = User.objects.create_user('viewer')
        self.client.force_login(viewer)
        for route in ('analytics', 'review_queue', 'obligations', 'gap_create'):
            self.assertEqual(self.client.get(reverse('qa:' + route)).status_code, 403)
        admin = User.objects.create_superuser('admin', password='test')
        self.client.force_login(admin)
        for route in ('analytics', 'review_queue', 'obligations', 'gap_create', 'trust'):
            self.assertEqual(self.client.get(reverse('qa:' + route)).status_code, 200)

    def test_review_resolution_preserves_original_support_result(self):
        admin = User.objects.create_superuser('admin', password='test')
        q = QueryLog.objects.create(question='?', confidence_band='low', review_required=True, citation_verified=False)
        self.client.force_login(admin)
        self.client.post(reverse('qa:resolve_review', args=['answer', q.pk]), {'status': 'resolved', 'notes': 'Checked manually.'})
        q.refresh_from_db()
        self.assertEqual(q.reviewed_by, admin)
        self.assertEqual(q.review_status, 'resolved')
        self.assertFalse(q.citation_verified)
