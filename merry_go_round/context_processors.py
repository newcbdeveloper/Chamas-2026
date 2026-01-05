from constance import config

def mgr_settings(request):
    """Make MGR settings available in all templates"""
    return {
        'MGR_DEFAULT_INTEREST_RATE': config.MGR_DEFAULT_INTEREST_RATE,
        'MGR_TAX_RATE': config.MGR_TAX_RATE,
        'ROTATIONAL_MODEL_ENABLED': config.ROTATIONAL_MODEL_ENABLED,
        'MGR_INVITATION_VALIDITY_DAYS': config.MGR_INVITATION_VALIDITY_DAYS,
    }