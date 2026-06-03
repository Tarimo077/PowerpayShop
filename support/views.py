from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from notifications.utils import notify
from .forms import TicketForm
from .models import Ticket, TicketMessage


def is_admin(user):
    return user.is_authenticated and user.is_staff


def _safe_per_page(request, allowed=(5, 10, 20), default=5):
    value = request.GET.get("per_page", str(default))
    return int(value) if value in {str(v) for v in allowed} else default


@login_required
def create_ticket(request):
    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            return redirect("support_ticket_list")
    else:
        form = TicketForm()
    return render(request, "support/create_ticket.html", {"form": form})


@login_required
def ticket_list(request):
    per_page = _safe_per_page(request)
    tickets_qs = Ticket.objects.filter(user=request.user).order_by("-created_at")
    tickets = Paginator(tickets_qs, per_page).get_page(request.GET.get("page", 1))
    return render(request, "support/ticket_list.html", {"tickets": tickets, "per_page": per_page})


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.prefetch_related("messages__sender"), id=ticket_id, user=request.user)

    if request.method == "POST" and ticket.status != "closed":
        reply = request.POST.get("reply", "").strip()
        if reply:
            TicketMessage.objects.create(ticket=ticket, sender=request.user, message=reply)
            admins = User.objects.filter(is_staff=True).only("id")
            for admin in admins:
                notify(admin, f"New Message | Ticket #{ticket.id}", f"{request.user.username} responded to a support ticket.", "warning")
        return redirect("ticket_detail", ticket_id=ticket_id)

    return render(request, "support/ticket_detail.html", {"ticket": ticket})


@user_passes_test(is_admin)
def admin_ticket_list(request):
    per_page = _safe_per_page(request, default=10)
    tickets_qs = Ticket.objects.select_related("user").order_by("-created_at")
    tickets = Paginator(tickets_qs, per_page).get_page(request.GET.get("page", 1))
    return render(request, "support/admin_ticket_list.html", {"tickets": tickets, "per_page": per_page})


@user_passes_test(is_admin)
def admin_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.select_related("user").prefetch_related("messages__sender"), id=ticket_id)

    if request.method == "POST":
        reply = request.POST.get("reply", "").strip()
        status = request.POST.get("status")

        if status and status != ticket.status:
            ticket.status = status
            ticket.save(update_fields=["status"])
            notify(ticket.user, f"Ticket #{ticket.id} Status Updated", f"Your support ticket status has changed to: {ticket.get_status_display()}", "info")

        if reply:
            TicketMessage.objects.create(ticket=ticket, sender=request.user, message=reply)
            notify(ticket.user, f"New Message | Ticket #{ticket.id}", "The support team has responded to your ticket.", "success")

        return redirect("admin_ticket_detail", ticket_id=ticket_id)

    return render(request, "support/admin_ticket_detail.html", {"ticket": ticket, "messages_page": ticket.messages.all()})
