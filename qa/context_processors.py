from . import permissions as p


def roles(request):
    """Expose role-derived flags to templates (display only; views enforce access)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'user_role': '', 'perms_flags': {}}
    return {
        'user_role': p.user_role(user),
        'perms_flags': {
            'upload': user.has_perm(p.PERM_UPLOAD),
            'index': user.has_perm(p.PERM_INDEX),
            'delete': user.has_perm(p.PERM_DELETE),
            'manage_corpus': user.has_perm(p.PERM_MANAGE_CORPUS),
            'global_logs': user.has_perm(p.PERM_GLOBAL_LOGS),
            'run_eval': user.has_perm(p.PERM_RUN_EVAL),
            'review_obligation': user.has_perm(p.PERM_REVIEW_OBLIGATION),
            'extract_obligations': user.has_perm(p.PERM_EXTRACT_OBLIGATIONS),
            'run_gap': user.has_perm(p.PERM_RUN_GAP),
            'analytics': user.has_perm(p.PERM_VIEW_ANALYTICS),
            'review_queue': user.has_perm(p.PERM_REVIEW_QUEUE),
        },
    }
