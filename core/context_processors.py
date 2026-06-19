from django.utils import timezone
from django.db.models import F
import logging

logger = logging.getLogger(__name__)


def complete_expired_investments(request):
    """
    Context processor that automatically processes daily profits and completes expired investments
    for the authenticated user on every page render.
    
    Runs for every authenticated user accessing any template.
    - Updates daily profits for active investments
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
        
        # First, process daily profits for all active investments that haven't expired
        active_investments = Investment.objects.filter(
            user=request.user,
            is_active=True,
            end_date__gt=now
        )
        
        for investment in active_investments:
            try:
                profit_added = investment.update_profit()
                if profit_added > 0:
                    logger.info(
                        f"Added daily profit of ${profit_added} for investment {investment.plan_id} for {request.user.email}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to update daily profit for investment {investment.plan_id}: {e}",
                    exc_info=True
                )
        
        # Then, find all active investments that have reached their end_date and complete them
        expired_investments = Investment.objects.filter(
            user=request.user,
            is_active=True,
            end_date__lte=now
        )
        
        # Process each expired investment
        for investment in expired_investments:
            try:
                # First, process any final daily profit before completion
                investment.update_profit()
                
                # Mark as completed
                investment.is_active = False
                investment.status = 'COMPLETED'
                investment.save(update_fields=['is_active', 'status'])
                
                # Add any remaining expected return to user's account balance
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
