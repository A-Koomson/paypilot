"""Recovery queue, drafts, approval and verified execution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.core.email import send_email
from apps.core.exceptions import ApiError
from apps.integrations.exceptions import PayPalError, PayPalTimeout
from apps.integrations.models import PayPalInvoice
from apps.integrations.paypal_client import remind_invoice
from apps.merchants.models import Merchant
from apps.policy.authorization import authorize
from apps.policy.idempotency import claim as claim_idempotency
from apps.recovery.models import (
    ALLOWED_TRANSITIONS,
    ActionState,
    DeliveryChannel,
    RecoveryAction,
    RecoveryCase,
    WorkflowStatus,
)
from apps.recovery.priority import days_overdue, explanation, score

OUTSTANDING_STATUSES = frozenset({"SENT", "UNPAID", "PARTIALLY_PAID", "PAYMENT_PENDING", "SCHEDULED"})
RESOLVED_STATUSES = frozenset({"PAID", "MARKED_AS_PAID", "CANCELLED", "REFUNDED", "MARKED_AS_REFUNDED"})
IN_FLIGHT = frozenset(
    {ActionState.DRAFT_PREPARED, ActionState.AWAITING_APPROVAL, ActionState.APPROVED, ActionState.EXECUTING}
)

COPY_DISCLOSURE = "Copying records the approved text for you to send yourself. PayPilot does not deliver it."
EMAIL_DISCLOSURE = "PayPilot will send this exact text only if SMTP email is configured and accepts the message."
PAYPAL_DISCLOSURE = (
    "PayPal POST /v2/invoicing/invoices/{id}/remind sends PayPal’s own reminder email. "
    "Custom subject and note are not honoured by PayPal."
)


def is_outstanding(invoice: PayPalInvoice) -> bool:
    if invoice.status in RESOLVED_STATUSES or invoice.status == "DRAFT":
        return False
    if invoice.status in OUTSTANDING_STATUSES:
        return invoice.due_amount > 0
    return invoice.due_amount > 0


def _transition(case: RecoveryCase, new_status: str) -> None:
    if new_status == case.workflow_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(case.workflow_status, frozenset())
    if new_status not in allowed:
        raise ApiError(
            f"Cannot move a case from {case.workflow_status} to {new_status}.",
            code="invalid_state",
            status_code=409,
        )
    case.workflow_status = new_status
    if new_status == WorkflowStatus.RESOLVED:
        case.resolved_at = timezone.now()
    elif new_status == WorkflowStatus.IDENTIFIED:
        case.resolved_at = None
    case.save(update_fields=["workflow_status", "resolved_at", "updated_at"])


def refresh_cases(merchant: Merchant) -> int:
    """Create or resolve cases from imported invoices. Does not invent missing fields."""
    created = 0
    invoices = PayPalInvoice.objects.filter(merchant=merchant)
    for invoice in invoices:
        case = RecoveryCase.objects.filter(merchant=merchant, invoice=invoice).first()
        if is_outstanding(invoice):
            if case is None:
                RecoveryCase.objects.create(merchant=merchant, invoice=invoice)
                created += 1
            elif case.workflow_status == WorkflowStatus.RESOLVED:
                _transition(case, WorkflowStatus.IDENTIFIED)
        elif case is not None and case.workflow_status != WorkflowStatus.RESOLVED:
            if invoice.status in RESOLVED_STATUSES:
                _transition(case, WorkflowStatus.RESOLVED)
    return created


def _recommended_action(case: RecoveryCase, latest: RecoveryAction | None) -> str:
    invoice = case.invoice
    if latest and latest.state == ActionState.AWAITING_APPROVAL:
        return "Review and approve the prepared reminder."
    if latest and latest.state == ActionState.FAILED:
        return "Review the failed action. The previous attempt is still marked failed."
    if latest and latest.state == ActionState.APPROVED:
        return "Execute the approved reminder."
    if not invoice.recipient_email:
        return "Prepare a reminder. Recipient email is unavailable from PayPal on this invoice."
    if invoice.due_date is None:
        return "Prepare a reminder. Due date is unavailable from PayPal on this invoice."
    return "Prepare a payment reminder for merchant review."


def serialize_action(action: RecoveryAction | None) -> dict | None:
    if action is None:
        return None
    return {
        "id": str(action.id),
        "kind": action.kind,
        "delivery": action.delivery,
        "state": action.state,
        "recipient_email": action.recipient_email or None,
        "subject": action.subject,
        "body": action.body,
        "invoice_reference": action.invoice_reference,
        "amount": f"{action.amount:.2f}",
        "currency": action.currency,
        "delivery_disclosure": action.delivery_disclosure,
        "approved_at": action.approved_at,
        "executed_at": action.executed_at,
        "outcome": action.outcome or None,
        "outcome_detail": action.outcome_detail or None,
        "paypal_http_status": action.paypal_http_status,
        "created_at": action.created_at,
    }


def serialize_case(case: RecoveryCase, *, today: date | None = None) -> dict:
    today = today or timezone.now().date()
    invoice = case.invoice
    latest = case.actions.order_by("-created_at").first()
    overdue = days_overdue(invoice.due_date, today)
    return {
        "id": str(case.id),
        "invoice_id": str(invoice.id),
        "source_id": invoice.source_id,
        "invoice_number": invoice.invoice_number or None,
        "status": invoice.status,
        "amount": f"{invoice.amount:.2f}",
        "due_amount": f"{invoice.due_amount:.2f}",
        "currency": invoice.currency,
        "recipient_email": invoice.recipient_email or None,
        "recipient_available": bool(invoice.recipient_email),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "due_date_available": invoice.due_date is not None,
        "days_overdue": overdue,
        "overdue_duration_available": overdue is not None,
        "recommended_action": _recommended_action(case, latest),
        "last_follow_up_at": case.last_follow_up_at,
        "workflow_status": case.workflow_status,
        "merchant_priority": case.merchant_priority,
        "priority_score": score(case, today=today),
        "priority_explanation": explanation(case, today=today),
        "latest_action": serialize_action(latest),
    }


def list_queue(
    merchant: Merchant,
    *,
    status: str = "",
    currency: str = "",
    customer: str = "",
    sort: str = "priority",
) -> list[dict]:
    refresh_cases(merchant)
    today = timezone.now().date()
    qs = RecoveryCase.objects.filter(merchant=merchant).exclude(workflow_status=WorkflowStatus.RESOLVED)
    qs = qs.select_related("invoice")
    if status:
        qs = qs.filter(Q(workflow_status=status) | Q(invoice__status=status))
    if currency:
        qs = qs.filter(invoice__currency=currency.upper())
    if customer:
        qs = qs.filter(invoice__recipient_email__icontains=customer)
    items = [serialize_case(case, today=today) for case in qs]
    reverse_amount = sort == "-amount"
    if sort in {"amount", "-amount"}:
        items.sort(key=lambda row: Decimal(row["due_amount"]), reverse=reverse_amount)
    elif sort == "due_date":
        items.sort(key=lambda row: row["due_date"] or "9999-12-31")
    elif sort == "customer":
        items.sort(key=lambda row: (row["recipient_email"] or "\uffff").lower())
    elif sort == "age":
        items.sort(key=lambda row: row["days_overdue"] if row["days_overdue"] is not None else -10**9, reverse=True)
    elif sort == "currency":
        items.sort(key=lambda row: row["currency"])
    else:
        items.sort(key=lambda row: row["priority_score"], reverse=True)
    return items


def metrics(merchant: Merchant) -> dict:
    refresh_cases(merchant)
    outstanding: dict[str, Decimal] = {}
    follow_up: dict[str, Decimal] = {}
    resolved: dict[str, Decimal] = {}
    confirmed: dict[str, Decimal] = {}
    sent_count = 0
    failed_count = 0

    cases = RecoveryCase.objects.filter(merchant=merchant).select_related("invoice")
    for case in cases:
        currency = case.invoice.currency
        if case.workflow_status != WorkflowStatus.RESOLVED and is_outstanding(case.invoice):
            outstanding[currency] = outstanding.get(currency, Decimal("0")) + case.invoice.due_amount
            if case.last_follow_up_at:
                follow_up[currency] = follow_up.get(currency, Decimal("0")) + case.invoice.due_amount
        if case.workflow_status == WorkflowStatus.RESOLVED and case.invoice.status in {"PAID", "MARKED_AS_PAID"}:
            resolved[currency] = resolved.get(currency, Decimal("0")) + case.invoice.amount
            if case.actions.filter(outcome__in={"emailed", "paypal_reminded"}, state=ActionState.ACTION_COMPLETED).exists():
                confirmed[currency] = confirmed.get(currency, Decimal("0")) + case.invoice.amount

    actions = RecoveryAction.objects.filter(merchant=merchant)
    sent_count = actions.filter(state=ActionState.ACTION_COMPLETED, outcome__in={"emailed", "paypal_reminded"}).count()
    failed_count = actions.filter(state=ActionState.FAILED).count()

    def money_map(raw: dict[str, Decimal]) -> list[dict]:
        return [{"amount": f"{amt:.2f}", "currency": cur} for cur, amt in sorted(raw.items())]

    return {
        "outstanding_identified": money_map(outstanding),
        "value_with_follow_up": money_map(follow_up),
        "reminders_successfully_sent": sent_count,
        "payments_subsequently_confirmed": money_map(confirmed),
        "outstanding_resolved": money_map(resolved),
        "failed_actions": failed_count,
        "notes": [
            "Totals are computed per currency from imported invoices. Currencies are never mixed.",
            "A sent reminder is not recovered revenue.",
            "payments_subsequently_confirmed only includes invoices that later show PAID or MARKED_AS_PAID after a delivered reminder.",
        ],
    }


def _reference(invoice: PayPalInvoice) -> str:
    return invoice.invoice_number or invoice.source_id


def build_draft_text(invoice: PayPalInvoice, merchant: Merchant) -> tuple[str, str]:
    ref = _reference(invoice)
    due = invoice.due_date.isoformat() if invoice.due_date else "not provided by PayPal"
    overdue = days_overdue(invoice.due_date, timezone.now().date())
    if overdue is None:
        timing = "The due date is not available from PayPal."
    elif overdue > 0:
        timing = f"This invoice is {overdue} days past the PayPal due date."
    elif overdue == 0:
        timing = "This invoice is due today according to PayPal."
    else:
        timing = f"This invoice is due in {abs(overdue)} days according to PayPal."
    subject = f"Payment reminder for invoice {ref}"
    business = merchant.business_name or "our accounts team"
    recipient_line = invoice.recipient_email or "the invoice recipient (email unavailable from PayPal)"
    body = (
        f"Hello {recipient_line},\n\n"
        f"This is a reminder about invoice {ref}.\n"
        f"Original amount: {invoice.amount:.2f} {invoice.currency}\n"
        f"Amount still outstanding: {invoice.due_amount:.2f} {invoice.currency}\n"
        f"PayPal status: {invoice.status or 'unavailable'}\n"
        f"Due date: {due}\n"
        f"{timing}\n\n"
        "Please pay using the invoice issued by PayPal.\n\n"
        f"{business}\n"
        "Prepared in PayPilot from your imported invoice record."
    )
    return subject, body


def _get_owned_case(merchant: Merchant, case_id) -> RecoveryCase:
    case = RecoveryCase.objects.select_related("invoice").filter(merchant=merchant, pk=case_id).first()
    if case is None:
        raise ApiError("Recovery case not found.", code="not_found", status_code=404)
    return case


def _get_owned_action(merchant: Merchant, action_id) -> RecoveryAction:
    action = (
        RecoveryAction.objects.select_related("case", "case__invoice")
        .filter(merchant=merchant, pk=action_id)
        .first()
    )
    if action is None:
        raise ApiError("Recovery action not found.", code="not_found", status_code=404)
    return action


def prepare_draft(merchant: Merchant, case_id, *, actor, subject: str = "", body: str = "") -> RecoveryAction:
    authorize(user=actor, merchant=merchant, action="recovery.draft")
    case = _get_owned_case(merchant, case_id)
    invoice = case.invoice
    if not is_outstanding(invoice):
        raise ApiError("This invoice is not outstanding.", code="invalid_state", status_code=409)
    if case.actions.filter(state__in=IN_FLIGHT).exists():
        raise ApiError("An action is already in progress for this invoice.", code="duplicate_action", status_code=409)
    default_subject, default_body = build_draft_text(invoice, merchant)
    action = RecoveryAction.objects.create(
        case=case,
        merchant=merchant,
        recipient_email=invoice.recipient_email,
        subject=(subject or default_subject)[:200],
        body=body or default_body,
        invoice_reference=_reference(invoice),
        amount=invoice.due_amount,
        currency=invoice.currency,
        delivery_disclosure=COPY_DISCLOSURE,
        state=ActionState.DRAFT_PREPARED,
    )
    if case.workflow_status in {WorkflowStatus.IDENTIFIED, WorkflowStatus.NEEDS_REVIEW, WorkflowStatus.FAILED}:
        _transition(case, WorkflowStatus.DRAFT_PREPARED)
    audit.record(
        "recovery.draft_prepared",
        actor=actor,
        merchant=merchant,
        target_type="recovery_action",
        target_id=action.id,
        metadata={"invoice_id": str(invoice.id), "reference": action.invoice_reference},
    )
    return action


def submit_for_approval(merchant: Merchant, action_id, *, actor, delivery: str) -> RecoveryAction:
    authorize(user=actor, merchant=merchant, action="recovery.submit")
    if delivery not in DeliveryChannel.values:
        raise ApiError("Choose copy, email, or paypal_remind.", code="validation_error", status_code=400)
    action = _get_owned_action(merchant, action_id)
    if action.state != ActionState.DRAFT_PREPARED:
        raise ApiError("Only a prepared draft can be submitted for approval.", code="invalid_state", status_code=409)
    action.delivery = delivery
    if delivery == DeliveryChannel.PAYPAL_REMIND:
        action.delivery_disclosure = PAYPAL_DISCLOSURE
    elif delivery == DeliveryChannel.EMAIL:
        action.delivery_disclosure = EMAIL_DISCLOSURE
    else:
        action.delivery_disclosure = COPY_DISCLOSURE
    action.state = ActionState.AWAITING_APPROVAL
    action.save(update_fields=["delivery", "delivery_disclosure", "state", "updated_at"])
    _transition(action.case, WorkflowStatus.AWAITING_APPROVAL)
    audit.record(
        "recovery.submitted",
        actor=actor,
        merchant=merchant,
        target_type="recovery_action",
        target_id=action.id,
        metadata={"delivery": delivery},
    )
    return action


def approve_action(merchant: Merchant, action_id, *, actor, confirm: bool) -> RecoveryAction:
    authorize(user=actor, merchant=merchant, action="recovery.approve")
    if confirm is not True:
        raise ApiError("Set confirm=true to approve this specific action.", code="approval_required", status_code=403)
    action = _get_owned_action(merchant, action_id)
    if action.state != ActionState.AWAITING_APPROVAL:
        raise ApiError("This action is not awaiting approval.", code="invalid_state", status_code=409)
    action.state = ActionState.APPROVED
    action.approved_at = timezone.now()
    action.approved_by = actor
    action.save(update_fields=["state", "approved_at", "approved_by", "updated_at"])
    _transition(action.case, WorkflowStatus.APPROVED)
    audit.record(
        "recovery.approved",
        actor=actor,
        merchant=merchant,
        target_type="recovery_action",
        target_id=action.id,
        metadata={"delivery": action.delivery, "reference": action.invoice_reference},
    )
    return action


def reject_action(merchant: Merchant, action_id, *, actor) -> RecoveryAction:
    authorize(user=actor, merchant=merchant, action="recovery.reject")
    action = _get_owned_action(merchant, action_id)
    if action.state not in {ActionState.AWAITING_APPROVAL, ActionState.DRAFT_PREPARED}:
        raise ApiError("This action can no longer be rejected.", code="invalid_state", status_code=409)
    action.state = ActionState.REJECTED
    action.save(update_fields=["state", "updated_at"])
    _transition(action.case, WorkflowStatus.NEEDS_REVIEW)
    audit.record(
        "recovery.rejected",
        actor=actor,
        merchant=merchant,
        target_type="recovery_action",
        target_id=action.id,
    )
    return action


def execute_action(merchant: Merchant, action_id, *, actor, confirm: bool, idempotency_key: str) -> RecoveryAction:
    if confirm is not True:
        raise ApiError("Set confirm=true to execute this specific approved action.", code="approval_required", status_code=403)
    with transaction.atomic():
        action = (
            RecoveryAction.objects.select_for_update()
            .select_related("case", "case__invoice")
            .filter(merchant=merchant, pk=action_id)
            .first()
        )
        if action is None:
            raise ApiError("Recovery action not found.", code="not_found", status_code=404)
        authorize(
            user=actor,
            merchant=merchant,
            action="recovery.execute",
            record=action,
            approved=bool(action.approved_at) and action.state == ActionState.APPROVED,
            already_executed=action.state in {ActionState.ACTION_COMPLETED, ActionState.EXECUTING},
            eligible=is_outstanding(action.case.invoice),
            amount_valid=action.currency == action.case.invoice.currency and action.amount == action.case.invoice.due_amount,
        )
        claim_idempotency(
            merchant=merchant,
            action="recovery.execute",
            key=idempotency_key,
            payload={"action_id": str(action.id), "delivery": action.delivery},
            resource_type="recovery_action",
            resource_id=action.id,
        )
        action.idempotency_key = idempotency_key
        action.state = ActionState.EXECUTING
        action.save(update_fields=["idempotency_key", "state", "updated_at"])
        _transition(action.case, WorkflowStatus.EXECUTING)

    try:
        _deliver(action)
    except PayPalTimeout:
        _finish(action, failed=True, outcome="uncertain", detail="PayPal timed out after the request was sent. The reminder was not marked sent. Re-sync before retrying.")
        raise ApiError(
            "PayPal timed out. The reminder is marked uncertain, not sent.",
            code="paypal_timeout",
            status_code=504,
        )
    except PayPalError as exc:
        _finish(action, failed=True, outcome="failed", detail=exc.public_message, http_status=exc.status_code)
        raise ApiError(exc.public_message, code=exc.code, status_code=exc.status_code, details=exc.details)
    except ApiError:
        raise

    audit.record(
        "recovery.executed",
        actor=actor,
        merchant=merchant,
        target_type="recovery_action",
        target_id=action.id,
        metadata={"delivery": action.delivery, "outcome": action.outcome, "http_status": action.paypal_http_status},
    )
    return action


def _deliver(action: RecoveryAction) -> None:
    invoice = action.case.invoice
    if action.delivery == DeliveryChannel.COPY:
        _finish(action, failed=False, outcome="copied", detail=COPY_DISCLOSURE)
        return
    if action.delivery == DeliveryChannel.EMAIL:
        if not action.recipient_email:
            _finish(action, failed=True, outcome="failed", detail="Recipient email is unavailable from PayPal.")
            raise ApiError("Recipient email is unavailable from PayPal.", code="recipient_unavailable", status_code=409)
        result = send_email(to=action.recipient_email, subject=action.subject, body=action.body)
        if not result.delivered:
            _finish(
                action,
                failed=True,
                outcome="email_not_delivered",
                detail=f"Email backend mode is {result.mode}; the message was not delivered to the recipient.",
            )
            raise ApiError(
                "The reminder was not delivered. Email is not configured for outbound delivery.",
                code="email_not_delivered",
                status_code=503,
            )
        _finish(action, failed=False, outcome="emailed", detail=f"Accepted by SMTP for {action.recipient_email}.")
        return
    if action.delivery == DeliveryChannel.PAYPAL_REMIND:
        status = remind_invoice(invoice.source_id)
        _finish(
            action,
            failed=False,
            outcome="paypal_reminded",
            detail="PayPal returned 204 for POST /v2/invoicing/invoices/{id}/remind.",
            http_status=status,
        )
        return
    raise ApiError("Unsupported delivery channel.", code="unsupported_action", status_code=400)


def _finish(action: RecoveryAction, *, failed: bool, outcome: str, detail: str, http_status: int | None = None) -> None:
    action.outcome = outcome
    action.outcome_detail = detail[:400]
    action.paypal_http_status = http_status
    action.executed_at = timezone.now()
    action.state = ActionState.FAILED if failed else ActionState.ACTION_COMPLETED
    action.save(
        update_fields=["outcome", "outcome_detail", "paypal_http_status", "executed_at", "state", "updated_at"]
    )
    case = action.case
    if failed:
        _transition(case, WorkflowStatus.FAILED)
    else:
        case.last_follow_up_at = action.executed_at
        case.save(update_fields=["last_follow_up_at", "updated_at"])
        _transition(case, WorkflowStatus.ACTION_COMPLETED)
        if not is_outstanding(case.invoice):
            _transition(case, WorkflowStatus.RESOLVED)


def set_priority(merchant: Merchant, case_id, *, actor, priority: int) -> RecoveryCase:
    authorize(user=actor, merchant=merchant, action="recovery.draft")
    if priority < 0 or priority > 9:
        raise ApiError("Priority must be between 0 and 9.", code="validation_error", status_code=400)
    case = _get_owned_case(merchant, case_id)
    case.merchant_priority = priority
    case.save(update_fields=["merchant_priority", "updated_at"])
    return case
