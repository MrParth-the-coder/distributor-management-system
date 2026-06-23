import io
import random
import hashlib
from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import logout
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse, FileResponse

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .models import Distributor, DistributorActivityLog, DistributorPasswordResetOTP

# -------------------------
# Security & Logging Helpers
# -------------------------

def log_activity(request, email, action, distributor=None):
    """Logs client activity with IP, user agent, and timestamp."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    
    # Try to resolve distributor if not provided
    if not distributor and email:
        distributor = Distributor.objects.filter(email=email).first()
        
    DistributorActivityLog.objects.create(
        distributor=distributor,
        email=email,
        action=action,
        ip_address=ip,
        user_agent=user_agent
    )

def _get_logged_in_user(request):
    """Helper to check if session user exists and is active."""
    email = request.session.get('email')
    if not email:
        return None
    return Distributor.objects.filter(email=email, is_active=True).first()

# -------------------------
# Phase 2 & 3: Auth Views
# -------------------------

def register(request):
    if _get_logged_in_user(request):
        return redirect('profile')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('c_password', '')
        
        # Optional fields from Phase 2
        company_name = request.POST.get('company_name', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        profile_image = request.FILES.get('profile_image')

        # Back-end Security & Validation Checks
        if not username or not email or not phone or not password:
            messages.error(request, 'Please fill in all required fields.')
        elif password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        elif len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        elif Distributor.objects.filter(email=email).exists():
            messages.error(request, 'Email is already registered. Please choose another one.')
        elif Distributor.objects.filter(phone=phone).exists():
            messages.error(request, 'Phone number is already registered. Please choose another one.')
        else:
            # File validation
            if profile_image:
                ext = profile_image.name.split('.')[-1].lower()
                if ext not in ['jpg', 'jpeg', 'png']:
                    messages.error(request, 'Only JPG, JPEG, and PNG image files are supported.')
                    return render(request, 'register.html')
                if profile_image.size > 2 * 1024 * 1024:
                    messages.error(request, 'Profile image size must be less than 2MB.')
                    return render(request, 'register.html')

            # Hashed Password creation
            hashed_pw = make_password(password)
            user = Distributor(
                username=username,
                email=email,
                phone=phone,
                company_name=company_name,
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                profile_image=profile_image,
                password=hashed_pw
            )
            user.save()
            
            # Audit trail
            log_activity(request, email, 'REGISTER', distributor=user)
            
            messages.success(request, 'Registration successful! Please login below.')
            return redirect('login')

    return render(request, 'register.html')

def login(request):
    if _get_logged_in_user(request):
        return redirect('profile')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        try:
            user = Distributor.objects.get(email=email)
            if not user.is_active:
                messages.error(request, 'This account has been disabled.')
                log_activity(request, email, 'LOGIN_FAILED')
            elif check_password(password, user.password):
                # Setup session
                request.session['email'] = user.email
                if remember_me:
                    # Session lasts 2 weeks
                    request.session.set_expiry(1209600)
                else:
                    # Session expires on browser close
                    request.session.set_expiry(0)
                
                # Update login stats
                user.last_login = timezone.now()
                user.save()
                
                # Audit trail
                log_activity(request, email, 'LOGIN_SUCCESS', distributor=user)
                
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('profile')
            else:
                messages.error(request, 'Invalid password.')
                log_activity(request, email, 'LOGIN_FAILED', distributor=user)
        except Distributor.DoesNotExist:
            messages.error(request, 'User does not exist.')
            log_activity(request, email, 'LOGIN_FAILED')

    return render(request, 'login.html')

def user_logout(request):
    email = request.session.get('email')
    if email:
        distributor = Distributor.objects.filter(email=email).first()
        log_activity(request, email, 'LOGOUT', distributor=distributor)
        del request.session['email']
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('login')

# -------------------------
# Phase 5, 6, 15: Dashboard & Profile
# -------------------------

def profile(request):
    user = _get_logged_in_user(request)
    if not user:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('login')

    if request.method == 'POST':
        # Retrieve form data
        username = request.POST.get('username', '').strip()
        phone = request.POST.get('phone', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        profile_image = request.FILES.get('profile_image')
        clear_image = request.POST.get('clear_image')

        # Form validations
        if not username or not phone:
            messages.error(request, 'Name and Phone number are required fields.')
        elif Distributor.objects.filter(phone=phone).exclude(distributorid=user.distributorid).exists():
            messages.error(request, 'Phone number is already registered by another distributor.')
        else:
            # File validation
            if profile_image:
                ext = profile_image.name.split('.')[-1].lower()
                if ext not in ['jpg', 'jpeg', 'png']:
                    messages.error(request, 'Only JPG, JPEG, and PNG image files are supported.')
                    return redirect('profile')
                if profile_image.size > 2 * 1024 * 1024:
                    messages.error(request, 'Profile image size must be less than 2MB.')
                    return redirect('profile')
                
                # Delete old profile image if exists
                if user.profile_image:
                    try:
                        user.profile_image.delete(save=False)
                    except Exception:
                        pass
                user.profile_image = profile_image
            elif clear_image == 'true':
                if user.profile_image:
                    try:
                        user.profile_image.delete(save=False)
                    except Exception:
                        pass
                user.profile_image = None

            user.username = username
            user.phone = phone
            user.company_name = company_name
            user.address = address
            user.city = city
            user.state = state
            user.pincode = pincode
            user.save()
            
            # Audit trail
            log_activity(request, user.email, 'PROFILE_UPDATE', distributor=user)
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')

    # Load statistics
    completion_pct = user.profile_completion_percent()
    activity_count = DistributorActivityLog.objects.filter(email=user.email).count()
    recent_activities = DistributorActivityLog.objects.filter(email=user.email).order_by('-created_at')[:10]

    context = {
        'distributor': user,
        'completion_pct': completion_pct,
        'activity_count': activity_count,
        'recent_activities': recent_activities,
    }
    return render(request, 'profile.html', context)

# -------------------------
# Phase 8: Change Password
# -------------------------

def change_password(request):
    user = _get_logged_in_user(request)
    if not user:
        messages.error(request, "You must be logged in to access this page.")
        return redirect('login')

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not check_password(current_password, user.password):
            messages.error(request, 'Current password is incorrect.')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
        elif len(new_password) < 8:
            messages.error(request, 'New password must be at least 8 characters long.')
        else:
            user.password = make_password(new_password)
            user.save()
            log_activity(request, user.email, 'PASSWORD_CHANGE', distributor=user)
            messages.success(request, 'Password updated successfully!')
            return redirect('profile')

    return render(request, 'change_password.html')

# -------------------------
# Phase 9 & 10: Forgot Password & OTP System
# -------------------------

def forgot_password(request):
    if _get_logged_in_user(request):
        return redirect('profile')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = Distributor.objects.filter(email=email).first()

        if not user:
            messages.error(request, 'No distributor account is associated with this email.')
        else:
            # Generate 6 digit numeric OTP
            otp_code = f"{random.randint(100000, 999999)}"
            otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
            
            # Expiry in 10 minutes
            expires_at = timezone.now() + timezone.timedelta(minutes=10)
            
            # Store in database
            DistributorPasswordResetOTP.objects.create(
                distributor=user,
                email=email,
                otp_hash=otp_hash,
                expires_at=expires_at
            )
            
            # Audit trail
            log_activity(request, email, 'FORGOT_PASSWORD_REQUEST', distributor=user)
            
            # Send Email
            subject = "Your Password Reset OTP - Advanced Distributor System"
            message = f"Hello {user.username},\n\nYour OTP for resetting your password is: {otp_code}.\n\nThis OTP is valid for 10 minutes. Please do not share this OTP with anyone.\n\nBest Regards,\nAdvanced Distributor Support"
            
            email_sent = False
            try:
                send_mail(
                    subject,
                    message,
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as e:
                # Log email send failure but do not crash.
                print(f"[SMTP ERROR] Failed to send email to {email}: {e}")

            # Store email in session to verify OTP
            request.session['reset_email'] = email
            
            # Always print to console so development testing is simple
            print(f"\n[OTP DEBUG ALERT] Generated OTP for {email} is: {otp_code}\n")
            
            if email_sent:
                messages.success(request, 'An OTP has been sent to your email.')
            else:
                messages.warning(request, f'OTP generated successfully. (SMTP send failed. Dev/Testing OTP: {otp_code})')
            
            return redirect('verify_otp')

    return render(request, 'forgot_password.html')

def verify_otp(request):
    if _get_logged_in_user(request):
        return redirect('profile')

    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Session expired. Please request a new password reset OTP.')
        return redirect('forgot_password')

    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        otp_hash_entered = hashlib.sha256(otp_entered.encode()).hexdigest()

        # Find active valid OTP
        otp_record = DistributorPasswordResetOTP.objects.filter(
            email=email,
            otp_hash=otp_hash_entered,
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()

        if otp_record:
            # Mark OTP as used
            otp_record.is_used = True
            otp_record.save()

            log_activity(request, email, 'OTP_VERIFICATION', distributor=otp_record.distributor)
            
            # Set verified flag in session
            request.session['otp_verified'] = True
            messages.success(request, 'OTP verified successfully! Please enter your new password.')
            return redirect('reset_password')
        else:
            messages.error(request, 'Invalid or expired OTP. Please try again.')
            log_activity(request, email, 'RESET_PASSWORD_FAILED')

    return render(request, 'verify_otp.html')

def reset_password(request):
    if _get_logged_in_user(request):
        return redirect('profile')

    email = request.session.get('reset_email')
    verified = request.session.get('otp_verified')

    if not email or not verified:
        messages.error(request, 'Unauthorized. Please complete password recovery steps.')
        return redirect('forgot_password')

    if request.method == 'POST':
        new_password = request.POST.get('password', '')
        confirm_password = request.POST.get('c_password', '')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        elif len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        else:
            user = Distributor.objects.filter(email=email).first()
            if user:
                user.password = make_password(new_password)
                user.save()
                
                log_activity(request, email, 'RESET_PASSWORD_SUCCESS', distributor=user)
                
                # Clear session recovery keys
                del request.session['reset_email']
                del request.session['otp_verified']
                
                messages.success(request, 'Password has been reset successfully! Please login.')
                return redirect('login')
            else:
                messages.error(request, 'User does not exist.')
                return redirect('forgot_password')

    return render(request, 'reset_password.html')

# -------------------------
# Phase 11: Distributor Search Module
# -------------------------

def search_distributor(request):
    user = _get_logged_in_user(request)
    if not user:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('login')

    query = request.GET.get('q', '').strip()
    search_field = request.GET.get('field', 'all')
    sort_by = request.GET.get('sort', 'username')
    order = request.GET.get('order', 'asc')

    distributors = Distributor.objects.filter(is_active=True)

    # Filtering
    if query:
        if search_field == 'name':
            distributors = distributors.filter(username__icontains=query)
        elif search_field == 'email':
            distributors = distributors.filter(email__icontains=query)
        elif search_field == 'phone':
            distributors = distributors.filter(phone__icontains=query)
        elif search_field == 'company':
            distributors = distributors.filter(company_name__icontains=query)
        else:
            # All fields search
            distributors = distributors.filter(
                username__icontains=query) | distributors.filter(
                email__icontains=query) | distributors.filter(
                phone__icontains=query) | distributors.filter(
                company_name__icontains=query)

    # Sorting
    allowed_sort_fields = ['username', 'email', 'company_name', 'registration_date']
    if sort_by not in allowed_sort_fields:
        sort_by = 'username'

    order_prefix = '-' if order == 'desc' else ''
    distributors = distributors.order_by(f"{order_prefix}{sort_by}")

    # Pagination (5 records per page)
    paginator = Paginator(distributors, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'search_field': search_field,
        'sort_by': sort_by,
        'order': order,
    }
    return render(request, 'search.html', context)

# -------------------------
# Phase 12: PDF Export System
# -------------------------

def export_pdf(request):
    user = _get_logged_in_user(request)
    if not user:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('login')

    # Create byte buffer
    buffer = io.BytesIO()

    # Create document framework
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0d6efd'),
        spaceAfter=15
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=25
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1f2937'),
        spaceBefore=15,
        spaceAfter=10
    )
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#374151')
    )
    header_cell_style = ParagraphStyle(
        'HeaderCellStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("Advanced Distributor System", title_style))
    elements.append(Paragraph(f"Distributor Profile Report — Generated on {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", subtitle_style))
    elements.append(Spacer(1, 10))

    # Profile completion progress
    completion = user.profile_completion_percent()
    elements.append(Paragraph("Profile Overview", section_title))
    
    overview_data = [
        [Paragraph("Distributor ID", cell_style), Paragraph(str(user.distributorid), cell_style)],
        [Paragraph("Username", cell_style), Paragraph(user.username, cell_style)],
        [Paragraph("Email address", cell_style), Paragraph(user.email, cell_style)],
        [Paragraph("Phone number", cell_style), Paragraph(user.phone or "N/A", cell_style)],
        [Paragraph("Profile Completion", cell_style), Paragraph(f"{completion}%", cell_style)],
        [Paragraph("Status", cell_style), Paragraph("Active" if user.is_active else "Inactive", cell_style)],
    ]
    
    overview_table = Table(overview_data, colWidths=[200, 320])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9fafb')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(overview_table)
    elements.append(Spacer(1, 20))

    # Company & Address Information
    elements.append(Paragraph("Company & Address Details", section_title))
    company_data = [
        [Paragraph("Company Name", cell_style), Paragraph(user.company_name or "N/A", cell_style)],
        [Paragraph("Street Address", cell_style), Paragraph(user.address or "N/A", cell_style)],
        [Paragraph("City", cell_style), Paragraph(user.city or "N/A", cell_style)],
        [Paragraph("State", cell_style), Paragraph(user.state or "N/A", cell_style)],
        [Paragraph("Pincode", cell_style), Paragraph(user.pincode or "N/A", cell_style)],
    ]
    
    company_table = Table(company_data, colWidths=[200, 320])
    company_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9fafb')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(company_table)
    elements.append(Spacer(1, 25))

    # Document signature / footer space
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("I hereby certify that the above distributor details are correct and up-to-date.", cell_style))
    elements.append(Spacer(1, 30))
    
    sig_data = [
        [Paragraph("_____________________________<br/>Distributor Signature", cell_style),
         Paragraph("_____________________________<br/>Authorized Signatory", cell_style)]
    ]
    sig_table = Table(sig_data, colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(sig_table)

    # Build the PDF document
    doc.build(elements)

    # Rewind buffer
    buffer.seek(0)
    
    # Return File Response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"distributor_profile_{user.distributorid}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
