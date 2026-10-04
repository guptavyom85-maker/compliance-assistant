"""
Role-based access control helpers.

Roles are Django Groups created by ``python manage.py bootstrap_roles``:

* Viewer      – ask questions; view own answers and the document list.
* Contributor – Viewer + upload/index documents; review obligations; run gap analyses.
* Admin       – everything: delete documents, manage corpus/index, run evaluations,
                view global logs, analytics and the unified review queue.

Views must be protected with the decorators below; hiding a button in a
template is never treated as authorization.
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

ROLE_VIEWER = 'Viewer'
ROLE_CONTRIBUTOR = 'Contributor'
ROLE_ADMIN = 'Admin'

# Permission constants (app_label.codename)
PERM_UPLOAD = 'qa.upload_document'
PERM_INDEX = 'qa.index_document'
PERM_DELETE = 'qa.delete_document'
PERM_MANAGE_CORPUS = 'qa.manage_corpus'
PERM_GLOBAL_LOGS = 'qa.view_global_logs'
PERM_RUN_EVAL = 'qa.run_evaluation'
PERM_REVIEW_OBLIGATION = 'qa.review_obligation'
PERM_EXTRACT_OBLIGATIONS = 'qa.extract_obligations'
PERM_RUN_GAP = 'qa.run_gap_analysis'
PERM_VIEW_ANALYTICS = 'qa.view_global_logs'  # analytics are global data -> admin only
PERM_REVIEW_QUEUE = 'qa.view_global_logs'

VIEWER_PERMS: list[str] = [
    'qa.view_document',
]
CONTRIBUTOR_PERMS: list[str] = VIEWER_PERMS + [
    PERM_UPLOAD,
    PERM_INDEX,
    PERM_REVIEW_OBLIGATION,
    PERM_EXTRACT_OBLIGATIONS,
    PERM_RUN_GAP,
    'qa.view_obligation',
    'qa.view_gapanalysisrun',
]
ADMIN_PERMS: list[str] = CONTRIBUTOR_PERMS + [
    PERM_DELETE,
    PERM_MANAGE_CORPUS,
    PERM_GLOBAL_LOGS,
    PERM_RUN_EVAL,
    'qa.change_document',
    'qa.view_querylog',
    'qa.change_querylog',
    'qa.view_goldquestion',
    'qa.add_goldquestion',
    'qa.change_goldquestion',
    'qa.view_goldevidence',
    'qa.add_goldevidence',
    'qa.change_goldevidence',
    'qa.delete_goldevidence',
    'qa.view_evalrun',
    'qa.view_evalresult',
    'qa.change_evalresult',
    'qa.view_vectorindexbuild',
    'qa.change_gapfinding',
    'qa.view_gapfinding',
    'qa.change_obligation',
]

ROLE_PERMISSIONS = {
    ROLE_VIEWER: VIEWER_PERMS,
    ROLE_CONTRIBUTOR: CONTRIBUTOR_PERMS,
    ROLE_ADMIN: ADMIN_PERMS,
}


def user_role(user) -> str:
    if not user.is_authenticated:
        return ''
    if user.is_superuser:
        return ROLE_ADMIN
    names = set(user.groups.values_list('name', flat=True))
    for role in (ROLE_ADMIN, ROLE_CONTRIBUTOR, ROLE_VIEWER):
        if role in names:
            return role
    return ''


def require_perm(*perms):
    """Require login (redirect) and all given permissions (HTTP 403 otherwise)."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if perms and not request.user.has_perms(perms):
                raise PermissionDenied('You do not have permission to perform this action.')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def can_view_query(user, query_log) -> bool:
    return user.has_perm(PERM_GLOBAL_LOGS) or (query_log.user_id is not None and query_log.user_id == user.id)
