from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChoreDefinitionForm, HouseholdSetupForm, MemberRenameForm
from .models import ChoreDefinition, HouseholdMember


def home(request):
    members = list(HouseholdMember.objects.all())
    if len(members) != 2:
        return redirect("chores:setup")

    active_member_id = request.session.get("active_member_id")
    if active_member_id not in {member.id for member in members}:
        active_member_id = members[0].id
        request.session["active_member_id"] = active_member_id

    return render(
        request,
        "chores/home.html",
        {"members": members, "active_member_id": active_member_id},
    )


def library(request):
    if HouseholdMember.objects.count() != 2:
        return redirect("chores:setup")
    chores = ChoreDefinition.objects.select_related("fixed_member").all()
    return render(request, "chores/library.html", {"chores": chores})


def chore_create(request):
    if HouseholdMember.objects.count() != 2:
        return redirect("chores:setup")
    form = ChoreDefinitionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Chore created.")
        return redirect("chores:library")
    return render(request, "chores/chore_form.html", {"form": form, "heading": "Add chore"})


def chore_edit(request, pk):
    if HouseholdMember.objects.count() != 2:
        return redirect("chores:setup")
    chore = get_object_or_404(ChoreDefinition, pk=pk)
    form = ChoreDefinitionForm(request.POST or None, instance=chore)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Chore updated.")
        return redirect("chores:library")
    return render(request, "chores/chore_form.html", {"form": form, "heading": "Edit chore", "chore": chore})


def chore_toggle(request, pk):
    if request.method != "POST":
        return redirect("chores:library")
    chore = get_object_or_404(ChoreDefinition, pk=pk)
    chore.is_active = not chore.is_active
    chore.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Chore {'activated' if chore.is_active else 'deactivated'}.")
    return redirect("chores:library")


def setup(request):
    if HouseholdMember.objects.count() >= 2:
        return redirect("chores:home")

    form = HouseholdSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            members = [
                HouseholdMember.objects.create(name=form.cleaned_data["member_one"]),
                HouseholdMember.objects.create(name=form.cleaned_data["member_two"]),
            ]
        request.session["active_member_id"] = members[0].id
        messages.success(request, "Household setup complete.")
        return redirect("chores:home")

    return render(request, "chores/setup.html", {"form": form})


def select_member(request):
    if request.method != "POST":
        return redirect("chores:home")

    member = get_object_or_404(HouseholdMember, pk=request.POST.get("member_id"))
    request.session["active_member_id"] = member.id
    return redirect("chores:home")


def settings(request):
    members = list(HouseholdMember.objects.all())
    if len(members) != 2:
        return redirect("chores:setup")

    selected_member_id = request.POST.get("member_id") if request.method == "POST" else None
    forms = {
        member.id: MemberRenameForm(
            request.POST if request.method == "POST" and str(member.id) == selected_member_id else None,
            prefix=f"member-{member.id}",
            initial={"name": member.name},
        )
        for member in members
    }

    if request.method == "POST":
        member = get_object_or_404(HouseholdMember, pk=selected_member_id)
        member_form = forms[member.id]
        if member_form.is_valid():
            member.name = member_form.cleaned_data["name"]
            member.save(update_fields=["name", "updated_at"])
            messages.success(request, "Member name updated.")
            return redirect("chores:settings")

    member_forms = [(member, forms[member.id]) for member in members]
    return render(request, "chores/settings.html", {"member_forms": member_forms})
