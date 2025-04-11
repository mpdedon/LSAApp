from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta

# Import ALL your relevant models and forms
from core.models import (
    Student, Guardian, Class, Session, Term, FeeAssignment,
    StudentFeeRecord, Payment, FinancialRecord
)
from core.forms import PaymentForm # Adjust import path

CustomUser = get_user_model()

class FinancialViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.admin_user = CustomUser.objects.create_superuser('admin', 'admin@example.com', 'password123', role='admin')
        cls.guardian_user = CustomUser.objects.create_user('guardian1', 'g@e.com', 'password123', role='guardian')
        cls.other_user = CustomUser.objects.create_user('other', 'o@e.com', 'password123', role='student') # Non-admin

        # Create Session and Term
        cls.session = Session.objects.create(start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=150), is_active=True)
        cls.term = Term.objects.create(session=cls.session, name='First Term', start_date=date.today() - timedelta(days=30), end_date=date.today() + timedelta(days=60), is_active=True)

        # Create Classes
        cls.class1 = Class.objects.create(name='JSS 1')
        cls.class2 = Class.objects.create(name='JSS 2')

        # Create Guardian
        cls.guardian = Guardian.objects.create(user=cls.guardian_user, address="Test Address")

        # Create Students
        cls.student1_user = CustomUser.objects.create_user('s1', 's1@e.com', 'pw', role='student', first_name='Stud', last_name='One')
        cls.student1 = Student.objects.create(user=cls.student1_user, date_of_birth=date(2010, 1, 1), gender='M', current_class=cls.class1, student_guardian=cls.guardian, relationship='Son')
        cls.student2_user = CustomUser.objects.create_user('s2', 's2@e.com', 'pw', role='student', first_name='Stud', last_name='Two')
        cls.student2 = Student.objects.create(user=cls.student2_user, date_of_birth=date(2011, 1, 1), gender='F', current_class=cls.class1, student_guardian=cls.guardian, relationship='Daughter')
        cls.student3_user = CustomUser.objects.create_user('s3', 's3@e.com', 'pw', role='student', first_name='Stud', last_name='Three')
        cls.student3 = Student.objects.create(user=cls.student3_user, date_of_birth=date(2012, 1, 1), gender='M', current_class=cls.class2, student_guardian=cls.guardian, relationship='Son')


        # Create Fee Assignments
        cls.fee_assignment1 = FeeAssignment.objects.create(class_instance=cls.class1, term=cls.term, amount=Decimal('50000.00'))
        cls.fee_assignment2 = FeeAssignment.objects.create(class_instance=cls.class2, term=cls.term, amount=Decimal('60000.00'))

        # URLs
        cls.sfr_list_url = reverse('student_fee_record_list')
        cls.payment_list_url = reverse('payment_list')
        cls.payment_create_url = reverse('payment_create')
        cls.fin_rec_list_url = reverse('financial_record_list')

    def setUp(self):
        # Client for making requests
        self.client = Client()
        # Log in the admin user for most tests
        self.client.login(username='admin', password='password123')
        # Initial sync might be needed if setUpTestData doesn't trigger it
        # Or call sync within the specific view test GET methods
        # StudentFeeRecordListView().sync_fee_records(self.term) # Example direct call (use cautiously)

    # --- StudentFeeRecordListView Tests ---

    def test_sfr_list_view_get_authenticated_admin(self):
        """Test GET request by admin user."""
        response = self.client.get(self.sfr_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'fee_assignment/student_fee_record_accordion.html')
        self.assertIn('all_records_grouped_by_class', response.context)
        self.assertIn(self.class1.id, response.context['all_records_grouped_by_class'])
        self.assertIn(self.class2.id, response.context['all_records_grouped_by_class'])
        self.assertEqual(len(response.context['all_records_grouped_by_class'][self.class1.id]['records']), 2) # Stud1, Stud2
        self.assertEqual(len(response.context['all_records_grouped_by_class'][self.class2.id]['records']), 1) # Stud3

    def test_sfr_list_view_authentication_redirect(self):
        """Test unauthenticated users are redirected."""
        self.client.logout()
        response = self.client.get(self.sfr_list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_sfr_list_view_permission_redirect(self):
        """Test non-admin users are redirected."""
        self.client.logout()
        self.client.login(username='other', password='password123') # Login as non-admin
        response = self.client.get(self.sfr_list_url)
        self.assertEqual(response.status_code, 302) # Or 403 depending on mixin
        # self.assertIn(reverse('login'), response.url) # Or check for permission denied page

    def test_sfr_list_view_sync_on_get(self):
        """Test that sync creates missing records on GET."""
        # Ensure records don't exist initially (setUpTestData doesn't create them)
        self.assertEqual(StudentFeeRecord.objects.count(), 0)
        response = self.client.get(self.sfr_list_url)
        self.assertEqual(response.status_code, 200)
        # Check that records for students in assigned classes were created
        self.assertEqual(StudentFeeRecord.objects.count(), 3)
        self.assertTrue(StudentFeeRecord.objects.filter(student=self.student1, term=self.term).exists())
        self.assertTrue(StudentFeeRecord.objects.filter(student=self.student2, term=self.term).exists())
        self.assertTrue(StudentFeeRecord.objects.filter(student=self.student3, term=self.term).exists())

    def test_sfr_list_view_post_update_discount_single_class(self):
        """Test updating discounts via POST for one class."""
        # Ensure records exist first by making a GET request
        self.client.get(self.sfr_list_url)
        record1 = StudentFeeRecord.objects.get(student=self.student1, term=self.term)
        record2 = StudentFeeRecord.objects.get(student=self.student2, term=self.term)
        record3 = StudentFeeRecord.objects.get(student=self.student3, term=self.term) # Belongs to class2

        post_data = {
            'submitted_class_id': self.class1.id, # Submitting for JSS 1
            'record_id': [record1.id, record2.id], # Only IDs for students in this class form
            f'discount_{record1.id}': '3000.00', # Change discount for student 1
            f'discount_{record2.id}': record2.discount, # Keep discount same for student 2
            # Waiver fields might be absent if checkboxes aren't checked
        }
        response = self.client.post(self.sfr_list_url, data=post_data)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{self.sfr_list_url}#collapse-{self.class1.id}")

        # Verify changes
        record1.refresh_from_db()
        record2.refresh_from_db()
        record3.refresh_from_db() # Should be unchanged

        self.assertEqual(record1.discount, Decimal('3000.00'))
        self.assertEqual(record1.net_fee, Decimal('47000.00')) # 50000 - 3000
        self.assertEqual(record2.discount, Decimal('0.00')) # Unchanged from default
        self.assertEqual(record2.net_fee, Decimal('50000.00'))
        self.assertEqual(record3.discount, Decimal('0.00')) # Unchanged from default (different class)
        self.assertEqual(record3.net_fee, Decimal('60000.00'))

        # Verify FinancialRecord update via signal
        fr1 = FinancialRecord.objects.get(student=self.student1, term=self.term)
        self.assertEqual(fr1.total_discount, Decimal('3000.00'))
        self.assertEqual(fr1.total_fee, Decimal('47000.00'))

    def test_sfr_list_view_post_update_waiver_single_class(self):
        """Test updating waivers via POST for one class."""
        self.client.get(self.sfr_list_url) # Create records
        record1 = StudentFeeRecord.objects.get(student=self.student1, term=self.term)
        record2 = StudentFeeRecord.objects.get(student=self.student2, term=self.term)

        post_data = {
            'submitted_class_id': self.class1.id,
            'record_id': [record1.id, record2.id],
            # Discount fields are technically present even if not changed by user
            f'discount_{record1.id}': record1.discount,
            f'discount_{record2.id}': record2.discount,
            # Submit waiver for student 2 (value is the record ID)
            f'waiver_{record2.id}': record2.id,
            # Waiver for student 1 is NOT submitted (checkbox unchecked)
        }
        response = self.client.post(self.sfr_list_url, data=post_data)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{self.sfr_list_url}#collapse-{self.class1.id}")

        record1.refresh_from_db()
        record2.refresh_from_db()

        self.assertFalse(record1.waiver)
        self.assertEqual(record1.net_fee, Decimal('50000.00')) # Assuming 0 discount initially
        self.assertTrue(record2.waiver)
        self.assertEqual(record2.net_fee, Decimal('0.00'))

        fr2 = FinancialRecord.objects.get(student=self.student2, term=self.term)
        self.assertEqual(fr2.total_fee, Decimal('0.00')) # Net fee updated

    # --- PaymentView Tests ---

    def test_payment_create_view_get(self):
        response = self.client.get(self.payment_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payment/create_payment.html')
        self.assertIsInstance(response.context['form'], PaymentForm)

    def test_payment_create_view_post_valid(self):
        """Test creating a valid payment."""
        # Need a FinancialRecord to link to
        sfr = StudentFeeRecord.objects.create(student=self.student1, term=self.term, fee_assignment=self.fee_assignment, amount='50000')
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)

        payment_data = {
            'financial_record': fr.id,
            'amount_paid': '25000.00',
            'payment_date': date.today().isoformat()
        }
        response = self.client.post(self.payment_create_url, data=payment_data)

        self.assertEqual(response.status_code, 302) # Should redirect on success
        self.assertRedirects(response, self.payment_list_url)
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.financial_record, fr)
        self.assertEqual(payment.amount_paid, Decimal('25000.00'))

        # Check FinancialRecord update via signal
        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('25000.00'))
        self.assertEqual(fr.outstanding_balance, Decimal('25000.00')) # 50000 - 25000

    def test_payment_create_view_post_overpayment_invalid(self):
        """Test creating a payment that exceeds net fee."""
        sfr = StudentFeeRecord.objects.create(student=self.student1, term=self.term, fee_assignment=self.fee_assignment, amount='20000')
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term) # Net fee is 20k

        payment_data = {
            'financial_record': fr.id,
            'amount_paid': '25000.00', # Exceeds net fee
            'payment_date': date.today().isoformat()
        }
        response = self.client.post(self.payment_create_url, data=payment_data)

        self.assertEqual(response.status_code, 200) # Re-renders form on validation error
        self.assertFormError(response, 'form', None, 'would exceed net fee') # Check non-field error
        self.assertEqual(Payment.objects.count(), 0) # Payment not created

    def test_payment_delete_view(self):
        """Test deleting a payment updates financial record."""
        sfr = StudentFeeRecord.objects.create(student=self.student1, term=self.term, fee_assignment=self.fee_assignment, amount='50000')
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)
        payment = Payment.objects.create(financial_record=fr, amount_paid='10000')
        payment_delete_url = reverse('payment_delete', kwargs={'pk': payment.pk})

        # GET confirmation page
        response_get = self.client.get(payment_delete_url)
        self.assertEqual(response_get.status_code, 200)
        self.assertTemplateUsed(response_get, 'payment/delete_payment.html')

        # POST to delete
        response_post = self.client.post(payment_delete_url)
        self.assertEqual(response_post.status_code, 302)
        self.assertRedirects(response_post, self.payment_list_url)
        self.assertEqual(Payment.objects.count(), 0) # Payment deleted

        # Check FinancialRecord update via signal
        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('0.00'))
        self.assertEqual(fr.outstanding_balance, Decimal('50000.00'))


    # --- FinancialRecordListView Tests ---
    def test_financial_record_list_view_get(self):
        """Test GET request for financial records list."""
        # Create some records via SFR creation
        StudentFeeRecord.objects.create(student=self.student1, term=self.term, fee_assignment=self.fee_assignment, amount='50000', discount='5000') # Net 45k
        StudentFeeRecord.objects.create(student=self.student2, term=self.term, fee_assignment=self.fee_assignment, amount='50000') # Net 50k
        StudentFeeRecord.objects.create(student=self.student3, term=self.term, fee_assignment=self.fee_assignment2, amount='60000') # Net 60k

        fr1 = FinancialRecord.objects.get(student=self.student1)
        Payment.objects.create(financial_record=fr1, amount_paid='20000')

        response = self.client.get(self.fin_rec_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial_record/financial_record_list.html')
        self.assertIn('financial_records', response.context)
        self.assertEqual(len(response.context['financial_records']), 3)

        # Check calculated totals in context
        self.assertEqual(response.context['total_fee'], Decimal('45000.00') + Decimal('50000.00') + Decimal('60000.00'))
        self.assertEqual(response.context['total_discount'], Decimal('5000.00'))
        self.assertEqual(response.context['total_paid'], Decimal('20000.00'))
        expected_outstanding = (Decimal('45000.00') - Decimal('20000.00')) + Decimal('50000.00') + Decimal('60000.00')
        self.assertEqual(response.context['total_outstanding_balance'], expected_outstanding)