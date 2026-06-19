from celery import shared_task
from django.utils import timezone
from .models import Investment
from decimal import Decimal
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
        
        processed_count = 0
        for investment in active_investments:
            try:
                profit_added = investment.update_profit()
                if profit_added > Decimal('0'):
                    processed_count += 1
                    logger.info(
                        f"Added daily profit of ${profit_added} for investment {investment.plan_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to process daily profit for investment {investment.plan_id}: {e}"
                )
                
        return f"Processed {processed_count} investments with daily profits"
        
    except Exception as e:
        logger.error(f"Failed to process daily profits: {e}")
        raise
