from django.utils import timezone
from django.db.models import F
import logging

logger = logging.getLogger(__name__)


def complete_expired_investments(request):
    """
    Context processor that automatically completes all expired investments
    for the authenticated user on every page render.
    
    Runs for every authenticated user accessing any template.
    - Finds investments where end_date <= now and is_active=True
    - Marks them as COMPLETED
    - Adds expected_return to account_balance
    
    Returns empty dict (no template variables added).
    """
    # Only run for authenticated users
    if not request.user.is_authenticated:
        return {}
    
    try:
        from core.models import Investment
        from account.models import Profile
        
        now = timezone.now()
        
        # Find all active investments that have reached their end_date
        expired_investments = Investment.objects.filter(
            user=request.user,
            is_active=True,
            end_date__lte=now
        )
        
        # Process each expired investment
        for investment in expired_investments:
            try:
                # Mark as completed
                investment.is_active = False
                investment.status = 'COMPLETED'
                investment.save(update_fields=['is_active', 'status'])
                
                # Add expected return to user's account balance
                Profile.objects.filter(user=request.user).update(
                    account_balance=F('account_balance') + investment.expected_return
                )
                
                logger.info(
                    f"Auto-completed investment {investment.plan_id} for {request.user.email}: +${investment.expected_return}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to complete investment {investment.plan_id}: {e}",
                    exc_info=True
                )
    
    except Exception as e:
        logger.error(f"Error in complete_expired_investments context processor: {e}", exc_info=True)
    
    # Return empty context (we don't add template variables)
    return {}
