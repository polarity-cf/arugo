from datetime import time
from django.shortcuts import redirect, render
from .models import Profile, Problem, AuthQuery
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.hashers import make_password

from .util import *


def index(request):
    user = request.user

    context = {}
    context["user"] = None
    context["graph"] = None
    context["user"] = request.user
    context["user_count"] = len(User.objects.all())

    if request.user.is_authenticated:
        profile = Profile.objects.get(user=user)

        if request.method == "POST" and user.check_password(
            request.POST.get("password")
        ):
            return redirect("reset-progress")

        context["profile"] = profile
        context["graph"] = make_graph(profile.handle, eval(profile.rating_progress))
        context["xcolor"] = color_rating_2(profile.virtual_rating)
        context["state"] = profile.msg
        profile.msg = 0
        profile.save()
        history = eval(profile.history)

        context["history_data"] = []

        for contest_id, index, delta in history:
            problem = Problem.objects.get(contest_id=contest_id, index=index)
            color, bg_color = rating_color(problem.rating)
            context["history_data"].append((problem, color, bg_color, delta))

        context["history_data"].reverse()

    return render(request, "home.html", context)


def challenge_list(request):
    if not request.user.is_authenticated:
        return redirect("login")

    user = request.user
    profile = Profile.objects.get(user=user)

    if profile.in_progress:
        return redirect("challenge")

    fd = FetchData.objects.all()

    if fd[0].last_update + timedelta(hours=12) < timezone.now():
        update_problemset()
        fd[0].last_update = timezone.now()

    if request.method == "POST":
        contest_id = request.POST.get("contest_id")
        index = request.POST.get("index")

        if represents_int(contest_id):
            accept_challenge(profile, int(contest_id), index)
            return redirect("challenge")

    handle = profile.handle
    rating = profile.virtual_rating

    normalized_rating = rating - rating % 100
    context = {}
    context["user"] = user
    context["profile"] = profile
    context["state"] = profile.msg
    profile.msg = 0
    profile.save()
    context["challenges"] = get_challenge(
        handle,
        profile.virtual_rating,
        [normalized_rating + delta for delta in range(-200, 500, 100)],
    )

    return render(request, "list.html", context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home-page")

    context = {}
    context["error"] = []
    context["user"] = request.user

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            response = redirect("home-page")
            return response

        else:
            context["error"].append("Failed to login.")

    return render(request, "login.html", context)


def logout_view(request):
    logout(request)

    return redirect("/login/")


def register(request):
    if request.user.is_authenticated:
        return redirect("home-page")

    context = {}
    context["error"] = []
    context["contest_id"] = ""
    context["index"] = ""

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        rating = request.POST.get("rating")
        handle = username

        if not represents_int(rating):
            context["error"].append(("Rating is not an integer.", False))

        elif handle.count(" ") > 0 or not validate_handle(handle):
            context["error"].append(("This handle does not exists.", False))

        elif undergoing_auth_query(handle):
            query = AuthQuery.objects.filter(handle=handle)
            context["contest_id"] = query[0].contest_id
            context["index"] = query[0].index
            context["error"].append(("Submit a compile error submission at", True))

        else:
            rating = int(rating)
            rating = min(rating, 3500)
            rating = max(rating, 400)
            query = 1
            problem = get_random_problem()
            password = make_password(password)

            if AuthQuery.objects.filter(handle=handle).exists():
                query = AuthQuery.objects.get(handle=handle)
                query.valid = True
                query.password = password
                query.rating = rating
                query.index = problem.index
                query.contest_id = problem.contest_id
                query.date = timezone.now()
                query.save()

            else:
                query = AuthQuery(
                    valid=True,
                    handle=handle,
                    password=password,
                    rating=rating,
                    contest_id=problem.contest_id,
                    index=problem.index,
                    date=timezone.now(),
                )
                query.save()

            context["contest_id"] = query.contest_id
            context["index"] = query.index
            context["error"].append(("Submit a compile error submission at", True))

    return render(request, "register.html", context)


def validate(request):
    if request.user.is_authenticated:
        return redirect("home-page")

    context = {}
    context["error"] = []

    if request.method == "POST":
        handle = request.POST.get("handle")
        query = AuthQuery.objects.filter(handle=handle)

        if len(query) == 0:
            context["error"].append(
                ("No such handle authorization query been made.", False)
            )

        else:
            query = query[0]

            if validate_auth_query(query):
                context["error"].append(("Successful registered.", True))

            else:
                context["error"].append(("Validation failed.", False))
                if query.valid and timezone.now() > query.date + timedelta(minutes=2):
                    query.valid = False
                    query.save()
                    context["error"].append(
                        (
                            "The request has timed out. Please submit a new registration request.",
                            False,
                        )
                    )

    return render(request, "validate.html", context)


def challenge_site(request):
    if not request.user.is_authenticated:
        return redirect("home-page")

    user = request.user
    profile = Profile.objects.get(user=user)

    if not profile.in_progress:
        return redirect("list")

    if validate_challenge(profile):
        return redirect("list")

    profile.msg = 0
    profile.save()

    contest_id, index = parse_problem_id(profile.current_problem)
    problem = Problem.objects.get(contest_id=contest_id, index=index)
    color, bg_color = rating_color(problem.rating)

    context = {}
    context["problem"] = problem
    minutes, seconds = remaining_time_convert(
        (profile.deadline - timezone.now()).total_seconds()
    )
    context["minutes"] = minutes
    context["seconds"] = seconds
    context["color"] = color
    context["bg_color"] = bg_color
    context["gain"] = rating_gain(profile.virtual_rating, problem.rating)
    context["loss"] = rating_loss(profile.virtual_rating, problem.rating)
    context["user"] = request.user
    context["profile"] = profile
    context["xcolor"] = color_rating_2(problem.rating)

    return render(request, "challenge.html", context)


def solving(request, contest_id, index):
    if not request.user.is_authenticated:
        return redirect("home-page")

    user = request.user
    profile = Profile.objects.get(user=user)

    if profile.in_progress:
        return redirect("challenge")

    accept_challenge(profile, contest_id, index)

    return redirect("challenge")


def giveup(request):
    if not request.user.is_authenticated:
        return redirect("home-page")

    user = request.user
    profile = Profile.objects.get(user=user)

    if profile.in_progress:
        give_up_problem(profile)

    return redirect("list")


def reset_progress(request):
    if not request.user.is_authenticated:
        return redirect("home-page")

    user = request.user
    profile = Profile.objects.get(user=user)

    reset_rating_progress(profile)
    return redirect("home-page")


def help(request):
    context = {}
    context["user"] = request.user
    context["profile"] = None

    if request.user.is_authenticated:
        profile = Profile.objects.get(user=request.user)
        context["profile"] = profile

    return render(request, "help.html", context)


def discard(request):
    if not request.user.is_authenticated:
        return redirect("home-page")

    user = request.user
    profile = Profile.objects.get(user=user)

    discard_challenge(profile)

    return redirect("list")
