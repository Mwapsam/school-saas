import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import News, Sms, Event, Student, Employee, User, Batch, Guardian, StudentGuardianRelation
from utils.sms_client import SMSClient
from utils.validators import normalize_phone_number
from .base import TenantAwareService
from .exceptions import ValidationException, NotFoundException
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)


class CommunicationService(TenantAwareService[News]):
    def __init__(self, tenant):
        super().__init__(News, tenant)
        self.logger = ServiceLogger('communication', tenant)

    @logged_operation(action='create', resource_type='news', log_result=True)
    def create_news(
        self,
        title: str,
        content: str,
        author_id: str,
        is_published: bool = True,
        publish_date: date = None,
        user=None,
        **additional_data
    ) -> News:
        if publish_date is None:
            publish_date = date.today()

        author = self._get_user_by_id(author_id)

        news_data = {
            "title": title,
            "content": content,
            "author": author,
            "is_published": is_published,
            "publish_date": publish_date,
            "tenant": self.tenant,
            **additional_data
        }

        news = News.objects.create(**news_data)

        if is_published:
            self._notify_announcement(news)

        self.logger.log_create(
            resource_type='news',
            resource_id=str(news.id),
            user=user,
            details={
                'title': title,
                'author': f"{author.first_name} {author.last_name}",
                'is_published': is_published,
                'publish_date': str(publish_date)
            }
        )

        return news

    def _notify_announcement(self, news: News) -> None:
        """Fan a published announcement out through Notification Control
        (Configuration → Notification Control) to every active guardian.
        Best-effort — never breaks announcement creation."""
        try:
            from core.services.notification_service import NotificationService

            guardians = (
                Guardian.objects.filter(tenant=self.tenant, is_active=True)
                if hasattr(Guardian, "is_active")
                else Guardian.objects.filter(tenant=self.tenant)
            )
            recipients = [
                {
                    "id": g.id, "type": "guardian",
                    "phone": getattr(g, "mobile_phone", None) or getattr(g, "phone", None),
                    "email": getattr(g, "email", None),
                }
                for g in guardians
            ]
            NotificationService(self.tenant).dispatch(
                "announcement", "guardians", recipients,
                title=news.title,
                message=news.content or news.title,
            )
        except Exception:
            logger.exception("announcement notification dispatch failed")

    def get_batch_guardians(self, batch_id: str) -> List[Dict[str, Any]]:
        """
        Returns deduplicated guardians linked to any active student in the batch.
        Filters out guardians with no usable phone number.

        Each entry: {
            'guardian_id': str,
            'name': str,
            'phone': str,
            'relation': str,
            'student_ids': List[str],
            'student_names': List[str],
        }
        """
        relations = StudentGuardianRelation.objects.filter(
            tenant=self.tenant,
            student__student_batches__batch_id=batch_id,
            student__student_batches__is_active=True,
            guardian__is_active=True,
        ).exclude(
            guardian__mobile_phone__isnull=True
        ).exclude(
            guardian__mobile_phone=''
        ).select_related('guardian', 'student')

        # Deduplicate by guardian, collecting student info
        guardians_map = {}
        for rel in relations:
            g = rel.guardian
            s = rel.student
            if g.id not in guardians_map:
                guardians_map[g.id] = {
                    'guardian_id': str(g.id),
                    'name': f"{g.first_name} {g.last_name}",
                    'phone': g.mobile_phone,
                    'relation': rel.relation,
                    'student_ids': [],
                    'student_names': [],
                }
            if str(s.id) not in guardians_map[g.id]['student_ids']:
                guardians_map[g.id]['student_ids'].append(str(s.id))
                guardians_map[g.id]['student_names'].append(f"{s.first_name} {s.last_name}")

        return list(guardians_map.values())

    @logged_operation(action='send', resource_type='sms', log_result=True)
    def send_sms(
        self,
        phone: str,
        message: str,
        user=None,
        batch_id: Optional[str] = None,
        guardian_id: Optional[str] = None,
        student_id: Optional[str] = None,
        sender_id: Optional[str] = None,
    ) -> Sms:
        """
        Send SMS to a single phone number and record the result.
        Does not raise on provider failure — records the failure in the Sms row
        so bulk sends can continue through partial provider failures.
        """
        if not phone or not phone.strip():
            raise ValidationException("Phone number is required")

        if not message or not message.strip():
            raise ValidationException("Message cannot be empty")

        # Normalize phone
        normalized = normalize_phone_number(phone)
        if not normalized:
            raise ValidationException(f"Invalid phone number format: {phone}")

        # Create pending SMS record
        sms_record = Sms.objects.create(
            body=message,
            recipient=normalized,
            is_sent=False,
            status=Sms.STATUS_PENDING,
            sent_by=user,
            batch_id=batch_id,
            guardian_id=guardian_id,
            student_id=student_id,
            tenant=self.tenant,
        )

        # Attempt to send via Africa's Talking
        try:
            result = SMSClient.send_sms_detailed(
                recipients=normalized,
                message=message,
                sender_id=sender_id or self.tenant.name,
                enqueue=False,
            )

            if result.get('success'):
                sms_record.status = Sms.STATUS_SENT
                sms_record.is_sent = True
                sms_record.sent_at = timezone.now()
            else:
                sms_record.status = Sms.STATUS_FAILED
                sms_record.is_sent = False
                sms_record.error_message = result.get('error', 'Unknown error')

            sms_record.save()

        except Exception as e:
            logger.error(f"Error sending SMS to {normalized}: {e}", exc_info=True)
            sms_record.status = Sms.STATUS_FAILED
            sms_record.is_sent = False
            sms_record.error_message = str(e)
            sms_record.save()

        return sms_record

    @logged_operation(action='bulk_send', resource_type='sms', log_performance=True)
    def send_batch_sms(
        self,
        batch_id: str,
        message: str,
        guardian_ids: Optional[List[str]] = None,
        send_all: bool = False,
        user=None,
        chunk_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Send SMS to guardians of students in a batch.

        Args:
            batch_id: The batch to send to
            message: Message text (will be truncated/joined if >160 chars)
            guardian_ids: Specific guardian IDs to send to (None + send_all=False is error)
            send_all: If True, send to all guardians in the batch
            user: User performing the send
            chunk_size: SMS API recipients per call (default 100)

        Returns: {
            'total_recipients': int,
            'sent_successfully': int,
            'failed_to_send': int,
            'sms_records': List[Sms],
            'errors': List[{'guardian_id': str, 'phone': str, 'error': str}],
        }
        """
        if not message or not message.strip():
            raise ValidationException("Message cannot be empty")

        results = {
            'total_recipients': 0,
            'sent_successfully': 0,
            'failed_to_send': 0,
            'sms_records': [],
            'errors': [],
        }

        # Get all available guardians in batch
        all_guardians = self.get_batch_guardians(batch_id)

        # Filter to requested guardians
        if not send_all and guardian_ids:
            guardian_ids_set = set(guardian_ids)
            guardians = [g for g in all_guardians if g['guardian_id'] in guardian_ids_set]
        elif send_all:
            guardians = all_guardians
        else:
            raise ValidationException("Must specify guardian_ids or set send_all=True")

        if not guardians:
            results['errors'].append({'error': 'No guardians found for this batch'})
            return results

        results['total_recipients'] = len(guardians)

        # Build (guardian_info, normalized_phone) tuples, filtering out invalid phones
        guardian_phone_pairs = []
        for g in guardians:
            phone = g['phone']
            normalized = normalize_phone_number(phone)
            if normalized:
                guardian_phone_pairs.append((g, normalized))
            else:
                results['failed_to_send'] += 1
                results['errors'].append({
                    'guardian_id': g['guardian_id'],
                    'phone': phone,
                    'error': 'Invalid phone number format',
                })

        # Process in chunks
        for i in range(0, len(guardian_phone_pairs), chunk_size):
            chunk = guardian_phone_pairs[i:i+chunk_size]
            phones = [phone for _, phone in chunk]

            try:
                # Call SMS provider once per chunk
                result = SMSClient.send_sms_detailed(
                    recipients=phones,
                    message=message,
                    sender_id=self.tenant.name,
                    enqueue=False,
                )

                if result.get('success') and result.get('response'):
                    # Parse per-recipient status from response
                    recipients_status = result['response'].get('SMSMessageData', {}).get('Recipients', [])

                    for guardian_info, phone in chunk:
                        # Find this phone in the response
                        status_info = None
                        for rs in recipients_status:
                            if rs.get('number') == phone:
                                status_info = rs
                                break

                        if status_info and str(status_info.get('status', '')).lower() == 'success':
                            # SMS sent successfully
                            sms = Sms.objects.create(
                                body=message,
                                recipient=phone,
                                is_sent=True,
                                status=Sms.STATUS_SENT,
                                sent_by=user,
                                sent_at=timezone.now(),
                                batch_id=batch_id,
                                guardian_id=guardian_info['guardian_id'],
                                tenant=self.tenant,
                            )
                            results['sms_records'].append(sms)
                            results['sent_successfully'] += 1
                        else:
                            # SMS failed for this recipient
                            sms = Sms.objects.create(
                                body=message,
                                recipient=phone,
                                is_sent=False,
                                status=Sms.STATUS_FAILED,
                                sent_by=user,
                                sent_at=timezone.now(),
                                error_message=status_info.get('status') if status_info else 'No response from provider',
                                batch_id=batch_id,
                                guardian_id=guardian_info['guardian_id'],
                                tenant=self.tenant,
                            )
                            results['sms_records'].append(sms)
                            results['failed_to_send'] += 1
                            results['errors'].append({
                                'guardian_id': guardian_info['guardian_id'],
                                'phone': phone,
                                'error': status_info.get('status') if status_info else 'No response',
                            })
                else:
                    # Whole chunk call failed
                    error_msg = result.get('error', 'Unknown provider error')
                    for guardian_info, phone in chunk:
                        sms = Sms.objects.create(
                            body=message,
                            recipient=phone,
                            is_sent=False,
                            status=Sms.STATUS_FAILED,
                            sent_by=user,
                            error_message=error_msg,
                            batch_id=batch_id,
                            guardian_id=guardian_info['guardian_id'],
                            tenant=self.tenant,
                        )
                        results['sms_records'].append(sms)
                        results['failed_to_send'] += 1
                        results['errors'].append({
                            'guardian_id': guardian_info['guardian_id'],
                            'phone': phone,
                            'error': error_msg,
                        })

            except Exception as e:
                logger.error(f"Error sending SMS chunk: {e}", exc_info=True)
                # Mark entire chunk as failed
                error_msg = str(e)
                for guardian_info, phone in chunk:
                    sms = Sms.objects.create(
                        body=message,
                        recipient=phone,
                        is_sent=False,
                        status=Sms.STATUS_FAILED,
                        sent_by=user,
                        error_message=error_msg,
                        batch_id=batch_id,
                        guardian_id=guardian_info['guardian_id'],
                        tenant=self.tenant,
                    )
                    results['sms_records'].append(sms)
                    results['failed_to_send'] += 1
                    results['errors'].append({
                        'guardian_id': guardian_info['guardian_id'],
                        'phone': phone,
                        'error': error_msg,
                    })

        return results

    @logged_operation(action='create', resource_type='event', log_result=True)
    def create_event(
        self,
        title: str,
        description: str,
        start_date: date,
        end_date: date = None,
        location: str = None,
        is_published: bool = True,
        user=None,
        **additional_data
    ) -> Event:
        if end_date and end_date < start_date:
            raise ValidationException(
                "Event end date must be after start date",
                details={"start_date": start_date, "end_date": end_date}
            )

        event_data = {
            "title": title,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
            "location": location,
            "is_published": is_published,
            "tenant": self.tenant,
            **additional_data
        }

        event = Event.objects.create(**event_data)

        self.logger.log_create(
            resource_type='event',
            resource_id=str(event.id),
            user=user,
            details={
                'title': title,
                'start_date': str(start_date),
                'end_date': str(end_date) if end_date else None,
                'location': location,
                'is_published': is_published
            }
        )

        return event

    def get_published_news(
        self,
        limit: int = None,
        start_date: date = None,
        end_date: date = None
    ) -> QuerySet[News]:
        query = Q(tenant=self.tenant, is_published=True)

        if start_date:
            query &= Q(publish_date__gte=start_date)

        if end_date:
            query &= Q(publish_date__lte=end_date)

        queryset = News.objects.filter(query).order_by('-publish_date')

        if limit:
            queryset = queryset[:limit]

        return queryset

    def get_upcoming_events(
        self,
        limit: int = None,
        days_ahead: int = 30
    ) -> QuerySet[Event]:
        from datetime import timedelta

        today = date.today()
        future_date = today + timedelta(days=days_ahead)

        query = Q(
            tenant=self.tenant,
            is_published=True,
            start_date__gte=today,
            start_date__lte=future_date
        )

        queryset = Event.objects.filter(query).order_by('start_date')

        if limit:
            queryset = queryset[:limit]

        return queryset

    def get_sms_history(
        self,
        batch_id: str = None,
        status: str = None,
        start_date: date = None,
        end_date: date = None,
        limit: int = None
    ) -> QuerySet[Sms]:
        query = Q(tenant=self.tenant)

        if batch_id:
            query &= Q(batch_id=batch_id)

        if status:
            query &= Q(status=status)

        if start_date:
            query &= Q(created_at__date__gte=start_date)

        if end_date:
            query &= Q(created_at__date__lte=end_date)

        queryset = Sms.objects.filter(query).order_by('-created_at')

        if limit:
            queryset = queryset[:limit]

        return queryset

    def get_communication_statistics(self) -> Dict[str, Any]:
        stats = {}

        stats['total_news'] = News.objects.filter(tenant=self.tenant).count()
        stats['published_news'] = News.objects.filter(
            tenant=self.tenant,
            is_published=True
        ).count()

        total_sms = Sms.objects.filter(tenant=self.tenant).count()
        sent_sms = Sms.objects.filter(tenant=self.tenant, status=Sms.STATUS_SENT).count()
        failed_sms = Sms.objects.filter(tenant=self.tenant, status=Sms.STATUS_FAILED).count()

        stats['total_sms'] = total_sms
        stats['sent_sms'] = sent_sms
        stats['failed_sms'] = failed_sms
        stats['sms_success_rate'] = round((sent_sms / total_sms * 100), 2) if total_sms > 0 else 0

        stats['total_events'] = Event.objects.filter(tenant=self.tenant).count()
        stats['published_events'] = Event.objects.filter(
            tenant=self.tenant,
            is_published=True
        ).count()

        return stats

    def _get_user_by_id(self, user_id: str) -> User:
        try:
            return User.objects.get(
                id=user_id,
                tenants=self.tenant,
                is_active=True
            )
        except User.DoesNotExist:
            raise NotFoundException(
                f"User with id {user_id} not found",
                details={"user_id": user_id}
            )

    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)

        required_fields = ['title', 'content']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationException(
                    f"Required field '{field}' is missing or empty",
                    details={"field": field}
                )

        title = data.get('title')
        if title and len(title) > 255:
            raise ValidationException(
                "Title is too long (maximum 255 characters)",
                details={"title_length": len(title), "max_length": 255}
            )
