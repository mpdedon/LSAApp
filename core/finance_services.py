from decimal import Decimal
import uuid

from django.db import transaction

from core.models import Class, FeeAssignment, FinancialRecord, Guardian, Payment, PaymentReceipt, Student, StudentFeeRecord, Term


def _generate_receipt_reference(scope, payment_date):
    scope_code = {
        'single': 'SGL',
        'guardian': 'GRD',
        'class': 'CLS',
    }.get(scope, 'PAY')
    date_part = (payment_date or Term.objects.order_by('-start_date').first().start_date).strftime('%Y%m%d') if payment_date else '00000000'
    return f"{scope_code}-{date_part}-{uuid.uuid4().hex[:6].upper()}"


def get_previous_term(target_term):
    if not target_term:
        return None
    return (
        Term.objects.exclude(pk=target_term.pk)
        .filter(start_date__lt=target_term.start_date)
        .order_by('-start_date', '-pk')
        .first()
    )


def summarize_fee_rollover(source_term, target_term):
    source_assignments = list(
        FeeAssignment.objects.filter(term=source_term).select_related('class_instance')
    )
    existing_target_class_ids = set(
        FeeAssignment.objects.filter(
            term=target_term,
            class_instance_id__in=[assignment.class_instance_id for assignment in source_assignments],
        ).values_list('class_instance_id', flat=True)
    )
    return {
        'source_term': source_term,
        'target_term': target_term,
        'source_assignments': source_assignments,
        'existing_count': len(existing_target_class_ids),
        'creatable_count': sum(1 for assignment in source_assignments if assignment.class_instance_id not in existing_target_class_ids),
        'existing_target_class_ids': existing_target_class_ids,
    }


def _rebuild_financial_records(term, student_ids):
    for student_id in student_ids:
        fin_record, _ = FinancialRecord.objects.get_or_create(student_id=student_id, term=term)
        fin_record.update_record()
        fin_record.save(update_fields=['total_fee', 'total_discount', 'total_paid', 'outstanding_balance', 'archived'])


@transaction.atomic
def sync_student_fee_records_for_term(
    target_term,
    source_term=None,
    class_ids=None,
    carry_forward_adjustments=True,
    active_only=True,
):
    assignments_qs = FeeAssignment.objects.filter(term=target_term).select_related('class_instance')
    if class_ids:
        assignments_qs = assignments_qs.filter(class_instance_id__in=class_ids)
    assignments = list(assignments_qs)
    if not assignments:
        return {'created': 0, 'updated': 0, 'skipped': 0, 'affected_students': 0}

    assignments_by_class_id = {assignment.class_instance_id: assignment for assignment in assignments}
    student_qs = Student.objects.filter(current_class_id__in=assignments_by_class_id.keys()).select_related('current_class')
    if active_only:
        student_qs = student_qs.filter(status='active')
    students = list(student_qs)
    if not students:
        return {'created': 0, 'updated': 0, 'skipped': 0, 'affected_students': 0}

    existing_records = StudentFeeRecord.objects.filter(
        term=target_term,
        student_id__in=[student.pk for student in students],
        fee_assignment_id__in=[assignment.pk for assignment in assignments],
    )
    existing_map = {(record.student_id, record.fee_assignment_id): record for record in existing_records}

    previous_map = {}
    if source_term and carry_forward_adjustments:
        previous_records = StudentFeeRecord.objects.filter(
            term=source_term,
            student_id__in=[student.pk for student in students],
            fee_assignment__class_instance_id__in=assignments_by_class_id.keys(),
        ).select_related('fee_assignment')
        previous_map = {
            (record.student_id, record.fee_assignment.class_instance_id): record
            for record in previous_records
        }

    created_records = []
    records_to_update = []
    touched_student_ids = set()
    created_count = 0
    updated_count = 0
    skipped_count = 0

    for student in students:
        assignment = assignments_by_class_id.get(student.current_class_id)
        if not assignment:
            skipped_count += 1
            continue

        previous_record = previous_map.get((student.pk, assignment.class_instance_id))
        record = existing_map.get((student.pk, assignment.pk))
        carried_discount = previous_record.discount if previous_record else Decimal('0.00')
        carried_waiver = previous_record.waiver if previous_record else False

        if record is None:
            created_records.append(
                StudentFeeRecord(
                    student=student,
                    term=target_term,
                    fee_assignment=assignment,
                    amount=assignment.amount,
                    discount=carried_discount if carry_forward_adjustments else Decimal('0.00'),
                    waiver=carried_waiver if carry_forward_adjustments else False,
                    net_fee=assignment.calculate_net_fee(
                        assignment.amount,
                        carried_discount if carry_forward_adjustments else Decimal('0.00'),
                        carried_waiver if carry_forward_adjustments else False,
                    ),
                )
            )
            touched_student_ids.add(student.pk)
            created_count += 1
            continue

        needs_save = False
        if record.amount != assignment.amount:
            record.amount = assignment.amount
            needs_save = True
        if record.fee_assignment_id != assignment.pk:
            record.fee_assignment = assignment
            needs_save = True
        if needs_save:
            records_to_update.append(record)
            touched_student_ids.add(student.pk)
            updated_count += 1
        else:
            skipped_count += 1

    if created_records:
        StudentFeeRecord.objects.bulk_create(created_records)
    for record in records_to_update:
        record.save()

    if touched_student_ids:
        _rebuild_financial_records(target_term, touched_student_ids)

    return {
        'created': created_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'affected_students': len(touched_student_ids),
    }


@transaction.atomic
def rollover_fee_assignments(
    source_term,
    target_term,
    overwrite_existing_assignments=False,
    carry_forward_adjustments=True,
):
    created_count = 0
    updated_count = 0
    skipped_count = 0
    touched_class_ids = []

    for source_assignment in FeeAssignment.objects.filter(term=source_term).select_related('class_instance'):
        target_assignment = FeeAssignment.objects.filter(
            term=target_term,
            class_instance=source_assignment.class_instance,
        ).first()

        if target_assignment is None:
            FeeAssignment.objects.create(
                class_instance=source_assignment.class_instance,
                term=target_term,
                amount=source_assignment.amount,
            )
            created_count += 1
            touched_class_ids.append(source_assignment.class_instance_id)
            continue

        if overwrite_existing_assignments and target_assignment.amount != source_assignment.amount:
            target_assignment.amount = source_assignment.amount
            target_assignment.save(update_fields=['amount'])
            updated_count += 1
            touched_class_ids.append(source_assignment.class_instance_id)
        else:
            skipped_count += 1
            touched_class_ids.append(source_assignment.class_instance_id)

    sync_summary = sync_student_fee_records_for_term(
        target_term,
        source_term=source_term,
        class_ids=touched_class_ids,
        carry_forward_adjustments=carry_forward_adjustments,
        active_only=True,
    )
    return {
        'created_assignments': created_count,
        'updated_assignments': updated_count,
        'skipped_assignments': skipped_count,
        'sync': sync_summary,
    }


def get_bulk_payment_candidates(scope, term, guardian=None, class_instance=None):
    queryset = FinancialRecord.objects.select_related(
        'student__user',
        'student__student_guardian__user',
        'student__current_class',
        'term__session',
    ).filter(
        term=term,
        student__status='active',
        total_fee__gt=Decimal('0.00'),
        outstanding_balance__gt=Decimal('0.00'),
    )

    if scope == 'guardian' and guardian:
        queryset = queryset.filter(student__student_guardian=guardian)
    elif scope == 'class' and class_instance:
        queryset = queryset.filter(student__current_class=class_instance)
    else:
        return FinancialRecord.objects.none()

    return queryset.order_by(
        'student__current_class__name',
        'student__user__last_name',
        'student__user__first_name',
        'student_id',
    )


def build_bulk_payment_preview(scope, term, total_amount=None, guardian=None, class_instance=None):
    records = list(get_bulk_payment_candidates(scope, term, guardian=guardian, class_instance=class_instance))
    requested_total = Decimal(str(total_amount or '0.00'))
    remaining = requested_total
    allocated_total = Decimal('0.00')
    total_outstanding = Decimal('0.00')
    preview_records = []

    for record in records:
        outstanding_balance = record.outstanding_balance or Decimal('0.00')
        total_outstanding += outstanding_balance
        suggested_allocation = Decimal('0.00')
        if remaining > Decimal('0.00'):
            suggested_allocation = min(outstanding_balance, remaining)
            remaining -= suggested_allocation
            allocated_total += suggested_allocation

        preview_records.append({
            'financial_record': record,
            'financial_record_id': record.pk,
            'student_name': record.student.user.get_full_name(),
            'class_name': record.student.current_class.name if record.student.current_class else 'Unassigned',
            'discount_amount': record.total_discount or Decimal('0.00'),
            'outstanding_balance': outstanding_balance,
            'suggested_allocation': suggested_allocation,
        })

    return {
        'records': preview_records,
        'candidate_count': len(preview_records),
        'requested_total': requested_total,
        'allocated_total': allocated_total,
        'remaining_amount': max(remaining, Decimal('0.00')),
        'total_outstanding': total_outstanding,
    }


def _clean_manual_allocations(preview, manual_allocations, total_amount):
    record_map = {str(entry['financial_record_id']): entry for entry in preview['records']}
    allocations = []
    allocated_total = Decimal('0.00')
    requested_total = Decimal(str(total_amount or '0.00')).quantize(Decimal('0.01'))

    for financial_record_id, raw_amount in manual_allocations:
        if str(financial_record_id) not in record_map:
            raise ValueError('One or more selected records no longer match this bulk payment scope.')
        amount = Decimal(str(raw_amount or '0.00'))
        if amount < Decimal('0.00'):
            raise ValueError('Manual allocations cannot be negative.')
        if amount == Decimal('0.00'):
            continue

        entry = record_map[str(financial_record_id)]
        if amount > entry['outstanding_balance'] + Decimal('0.01'):
            raise ValueError(f"Manual allocation for {entry['student_name']} exceeds the outstanding balance.")

        allocations.append((entry['financial_record'], amount))
        allocated_total += amount

    if not allocations:
        raise ValueError('Enter at least one manual allocation amount.')
    if allocated_total.quantize(Decimal('0.01')) > requested_total:
        raise ValueError('Manual allocations cannot exceed the total payment amount.')

    return allocations


def create_payment_receipt(
    payments,
    *,
    created_by=None,
    scope='single',
    guardian=None,
    student=None,
    term=None,
    batch_reference='',
    class_label='',
    preview=None,
):
    payments = list(payments)
    if not payments:
        return None

    preview_map = {}
    if preview:
        preview_map = {str(entry['financial_record_id']): entry for entry in preview.get('records', [])}

    first_payment = payments[0]
    resolved_reference = (batch_reference or '').strip() or _generate_receipt_reference(scope, first_payment.payment_date)
    line_items = []
    for payment in payments:
        payment.financial_record.refresh_from_db(fields=['outstanding_balance', 'total_discount'])
        preview_entry = preview_map.get(str(payment.financial_record_id), {})
        line_items.append({
            'payment_id': payment.pk,
            'financial_record_id': payment.financial_record_id,
            'student_id': payment.financial_record.student_id,
            'student_name': payment.student.user.get_full_name(),
            'class_name': payment.student.current_class.name if payment.student.current_class else 'Unassigned',
            'discount_amount': str(preview_entry.get('discount_amount', payment.financial_record.total_discount or Decimal('0.00'))),
            'outstanding_balance': str(payment.financial_record.outstanding_balance or Decimal('0.00')),
            'fee_category': 'School Fees',
            'amount_paid': str(payment.amount_paid),
        })

    receipt = PaymentReceipt.objects.create(
        term=term or first_payment.term,
        guardian=guardian,
        student=student,
        created_by=created_by,
        scope=scope,
        batch_reference=resolved_reference,
        class_label=class_label or '',
        total_amount=sum((payment.amount_paid for payment in payments), Decimal('0.00')),
        payment_date=first_payment.payment_date,
        line_items=line_items,
    )
    receipt.payments.add(*payments)
    return receipt


@transaction.atomic
def allocate_bulk_payment(
    scope,
    term,
    total_amount,
    payment_date,
    guardian=None,
    class_instance=None,
    batch_reference='',
    manual_allocations=None,
):
    preview = build_bulk_payment_preview(
        scope,
        term,
        total_amount=total_amount,
        guardian=guardian,
        class_instance=class_instance,
    )
    if not preview['records']:
        return {
            'created_payments': [],
            'allocated_total': Decimal('0.00'),
            'remaining_amount': Decimal('0.00'),
            'candidate_count': 0,
            'preview': preview,
        }

    if manual_allocations is None and preview['remaining_amount'] > Decimal('0.00'):
        raise ValueError('Payment amount exceeds the selected outstanding balances.')

    if manual_allocations is None:
        allocations = [
            (entry['financial_record'], entry['suggested_allocation'])
            for entry in preview['records']
            if entry['suggested_allocation'] > Decimal('0.00')
        ]
    else:
        allocations = _clean_manual_allocations(preview, manual_allocations, total_amount)

    created_payments = []

    for record, allocation in allocations:
        created_payments.append(
            Payment.objects.create(
                financial_record=record,
                amount_paid=allocation,
                payment_date=payment_date,
                batch_reference=(batch_reference or '').strip(),
            )
        )

    return {
        'created_payments': created_payments,
        'allocated_total': sum((payment.amount_paid for payment in created_payments), Decimal('0.00')),
        'remaining_amount': max(Decimal(str(total_amount or '0.00')) - sum((payment.amount_paid for payment in created_payments), Decimal('0.00')), Decimal('0.00')),
        'candidate_count': preview['candidate_count'],
        'preview': preview,
    }