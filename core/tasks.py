from celery import shared_task
from django.utils import timezone
from .models import Investment
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_daily_profits():
    """Process daily profits for all active investments"""
    try:
        active_investments = Investment.objects.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).select_related('user', 'type_plan')
        
        for investment in active_investments:
            try:
                profit_added = investment.update_profit()
                if profit_added:
                    logger.info(
                        f"Added daily profit of {profit_added} for investment {investment.plan_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to process daily profit for investment {investment.plan_id}: {e}"
                )
                
        return f"Processed {active_investments.count()} investments"
        
    except Exception as e:
        logger.error(f"Failed to process daily profits: {e}")
        raise
