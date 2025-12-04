from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Ticket
from .forms import TicketForm
from django.core.paginator import Paginator

@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            return redirect('support_ticket_list')
    else:
        form = TicketForm()
    return render(request, 'support/create_ticket.html', {'form': form})

@login_required
def ticket_list(request):
    per_page = int(request.GET.get("per_page", 5))  # default 6 per page
    page_number = request.GET.get("page", 1)

    tickets_qs = Ticket.objects.filter(user=request.user).order_by('-created_at')

    paginator = Paginator(tickets_qs, per_page)
    tickets = paginator.get_page(page_number)

    return render(request, "support/ticket_list.html", {
        "tickets": tickets,
        "per_page": per_page,
    })

# Admin views
def is_admin(user):
    return user.is_staff

@user_passes_test(is_admin)
def admin_ticket_list(request):
    per_page = int(request.GET.get("per_page", 10))
    page = request.GET.get("page", 1)

    tickets_qs = Ticket.objects.all().order_by('-created_at')
    paginator = Paginator(tickets_qs, per_page)
    tickets = paginator.get_page(page)

    return render(request, "support/admin_ticket_list.html", {
        "tickets": tickets,
        "per_page": per_page,
    })

@user_passes_test(is_admin)
def admin_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Ticket.STATUS_CHOICES):
            ticket.status = status
            ticket.save()
    return render(request, 'support/admin_ticket_detail.html', {'ticket': ticket})
