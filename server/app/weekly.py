"""Compose delivered owner ports. No test adapters or fake auth in production."""

import asyncio
import contextvars
import logging
from contextlib import asynccontextmanager, contextmanager
from copy import copy
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from server.app.config import Settings
from server.app.cycles import SerializedCycle
from server.app.errors import ServiceError
from server.app.main import create_app
from server.app.nudges import GuardedNudges
from server.app.operator import operator_registration
from server.app.planning_stores import (
    DurableClarifyStore,
    DurableSelectionStore,
)
from server.app.registry import ServiceRegistration
from server.app.stage import build_stage_router
from server.chat.api import build_router as chat_router
from server.chat.service import ChatService
from server.cycle import CycleService
from server.cycle.api import build_router as cycle_router
from server.cycle.api import install_cycle_error_handler
from server.cycle.wire import DailyAnswer, PrevalenceGuess
from server.matching.muse_specs import register_formation_specs
from server.matching.port import build_matching_port
from server.orchestration.api import build_router as orchestration_router
from server.orchestration.hooks import CycleHooks
from server.orchestration.runtime import MODEL_COMMUNITY, WeeklyRuntime, now_utc
from server.orchestration.wire import MuseCallEvidence
from server.planning import (
    ClarifyService,
    CycleQuestionPort,
    QuestionService,
    SyncClarify,
    VenueCatalog,
    load_default_bank,
    register_planning_tasks,
)
from server.planning.api import PlanningRuntime, install_planning_error_handler
from server.planning.api import build_router as planning_router
from server.privacy import (
    AnswerStore,
    LeasedSnapshot,
    ModerationStore,
    OutputGuard,
    PrivacyFormation,
    PrivacyService,
    SafetyScreener,
    actor_dependency,
    demo_population,
    install_privacy_error_handler,
    register_safety_task,
    session_token,
)
from server.privacy import build_router as privacy_router
from server.privacy.fixtures import seed_players
from server.privacy.sensitivity import register_sensitivity_task
from server.privacy.topics import register_activity_task
from server.providers import KeywordMusePort, TaskRegistry, build_muse_router, load_muse_config

VERIFIED_TOKEN = contextvars.ContextVar("verified_session_token", default=None)


class ScopedMuse:
    """Only approved model metadata is persisted, scoped to verified community."""

    def __init__(self, muse, repository):
        self.muse = muse
        self.repository = repository

    @property
    def configured(self):
        return self.muse.configured

    async def run(self, request):
        community = MODEL_COMMUNITY.get()
        if not community:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        result = await self.muse.run(request)
        evidence = MuseCallEvidence.model_validate(dict(result.evidence)).model_dump()
        with self.repository.transaction() as state:
            calls = state.records.setdefault("modelCalls", {}).setdefault(community, {})
            calls[str(uuid4())] = evidence
            while len(calls) > 500:
                calls.pop(next(iter(calls)))
        return result


class LeaseGuesses:
    def __init__(self, lease, answers):
        self.lease, self.answers = lease, answers

    async def prevalence_guesses(self, cycle_id):
        if cycle_id != self.lease.cycle_id:
            raise ServiceError("NOT_FOUND")
        result = {}
        for player in self.lease.player_ids:
            guess = self.answers.get_guess(cycle_id, player)
            if guess is not None:
                result[player] = guess.percent
        return result


def build_weekly_app(
    *,
    repository,
    privacy_store,
    muse_factory=None,
    clock=now_utc,
    settings: Settings | None = None,
    start_worker=True,
    transcriber=None,
):
    registry = register_planning_tasks(TaskRegistry())
    register_safety_task(registry)
    register_formation_specs(registry)
    register_activity_task(registry)
    register_sensitivity_task(registry)
    base_muse = (
        muse_factory(registry)
        if muse_factory is not None
        # Measured per-task models (server/providers/router.py), MUSE_ROUTES can override.
        else build_muse_router(registry, load_muse_config())
    )
    muse = ScopedMuse(base_muse, repository)
    privacy = PrivacyService(privacy_store, clock=clock)
    answers = AnswerStore(
        privacy_store, privacy, answer_model=DailyAnswer, guess_model=PrevalenceGuess
    )
    moderation = ModerationStore(privacy_store, privacy)
    holder = {}
    formation = PrivacyFormation(
        privacy_store,
        answers,
        moderation,
        question_texts=lambda cycle_id, community_id: holder["cycles"].question_texts(
            cycle_id, community_id
        ),
    )
    guard, safety = OutputGuard(), SafetyScreener(muse)

    async def week_start(cycle_id):
        cycle = holder["cycles"].gate(cycle_id).cycle
        if MODEL_COMMUNITY.get() != cycle.communityId:
            raise ServiceError("NOT_FOUND")
        return cycle.weekStart

    questions = QuestionService(load_default_bank(), DurableSelectionStore(repository), week_start)
    clarify = SyncClarify(
        ClarifyService(muse, guard, DurableClarifyStore(repository)), questions.bank
    )
    screen = safety.sync_screen()
    from server.app.v3_routes import InMemoryDayStore as _Store
    from server.app.v3_routes import V3Scheduler

    v3_store = _Store()
    v3_scheduler = V3Scheduler(answers, KeywordMusePort(muse), guard, v3_store)

    async def _v3_run(cycle):
        try:
            await v3_scheduler.on_cycle(cycle)
        except Exception:  # a v3 failure never blocks the cycle, but it must be visible
            logging.getLogger(__name__).exception("v3 scheduler step failed")

    def _v3_tick(cycle):
        # Fire and forget. Cycle hooks run in async routes, in sync routes (threadpool, no
        # running loop) and in the worker, so fall back to the app loop captured at startup.
        try:
            asyncio.get_running_loop().create_task(_v3_run(cycle))
        except RuntimeError:
            loop = holder.get("loop")
            if loop is not None and loop.is_running():
                asyncio.run_coroutine_threadsafe(_v3_run(cycle), loop)

    hooks = CycleHooks(
        publish_cycle=lambda c: (
            holder["stage_note"](c),
            holder["runtime"].on_changed(c),
            _v3_tick(c),
        )[1],
        enqueue_formation=lambda c: holder["runtime"].on_locked(c),
        reveal_cycle=lambda c: holder["runtime"].on_revealed(c),
    )

    def synthetic_seeder(community_id, players):
        # This is the authorized operator synthetic-top-up feature, not an auth
        # stand-in. The owner refuses any real-player fixture/reused real ID.
        ids = seed_players(privacy_store, community_id, players)
        # Their Groups, approved event RSVPs and post topics (labels only; no text stored).
        demo_population.seed_activity(privacy_store, community_id)
        with repository.transaction() as state:
            labeled = state.records.setdefault("syntheticPlayers", {})
            for player_id in ids:
                labeled[player_id] = {"communityId": community_id}
        return ids

    # Provider callbacks relinquish only Kai's app lock; all owner DB transactions
    # are already closed. CycleService itself rechecks before saving the answer.
    service = CycleService(
        answers=answers,
        questions=CycleQuestionPort(questions),
        screen=lambda *args: holder["cycles"].provider_call(screen, *args),
        clarify=lambda *args: holder["cycles"].provider_call(clarify, *args),
        guard=guard.text_guard(),
        hooks=hooks,
        seed_synthetic=synthetic_seeder,
        clock=clock,
    )

    @contextmanager
    def after_provider(cycle_id, session):
        token = VERIFIED_TOKEN.get()
        actor = privacy.require_session(token)
        if (actor.player_id, actor.community_id) != (session.playerId, session.communityId):
            raise ServiceError("UNAUTHENTICATED")
        lease = formation.prepare_formation(cycle_id, actor.community_id)
        with formation.publish_guard(cycle_id, lease.revision, []):
            privacy.require_consent(privacy.require_session(token))
            yield

    cycles = holder["cycles"] = SerializedCycle(
        service,
        after_provider=after_provider,
        before_reveal=lambda cycle_id: holder["runtime"].can_reveal(cycle_id),
    )

    def matching_factory(lease, themes):
        return build_matching_port(
            muse=KeywordMusePort(muse),
            snapshots=LeasedSnapshot(lease),
            guesses=LeaseGuesses(lease, answers),
            guard=guard,
            themes=themes,
            approved_event_ids=VenueCatalog.load().event_ids(),
            precompute_threshold=None,
        )

    runtime = holder["runtime"] = WeeklyRuntime(
        repository=repository,
        cycles=cycles,
        privacy=privacy,
        formation=formation,
        guard=guard,
        matching_factory=matching_factory,
        clock=clock,
    )
    runtime.answers = answers
    chat = runtime.chat = ChatService(
        repository=repository,
        privacy=privacy,
        formation=formation,
        moderation=moderation,
        guard=guard,
        safety=safety,
        cycles=cycles,
        clock=clock,
    )
    base_session = actor_dependency(privacy)

    async def authorize(request: Request):
        actor = await run_in_threadpool(base_session, request)
        MODEL_COMMUNITY.set(actor.community_id)
        VERIFIED_TOKEN.set(session_token(request))
        runtime.drain_notices()
        return actor

    async def storage_ready():
        return await asyncio.to_thread(repository.ready)

    async def privacy_ready():
        return privacy.ready()

    async def model_ready():
        return muse.configured is True and await storage_ready()

    async def voice_ready():
        return transcriber is not None

    def calls(actor):
        with repository.transaction() as state:
            return list(state.records.get("modelCalls", {}).get(actor.community_id, {}).values())

    op = operator_registration(
        session_dependency=authorize,
        require_operator=privacy.require_operator,
        calls_source=calls,
        reports_source=lambda actor: [r.wire() for r in moderation.report_queue(actor)],
    )
    orchestrator = orchestration_router(runtime, chat, privacy, authorize)
    orchestrator.routes.extend(op.router.routes)
    cycle = cycle_router(
        cycles, authorize, transcriber=transcriber, require_consent=privacy.require_consent
    )
    voice = copy(cycle)
    voice.routes = [route for route in cycle.routes if route.path.startswith("/voice/")]
    cycle.routes = [route for route in cycle.routes if not route.path.startswith("/voice/")]
    matching = APIRouter()

    @matching.get("/operator/cycles/{cycleId}/formation-debug")
    def debug(cycleId: str, request: Request):
        actor = request.state.cst_actor
        privacy.require_operator(actor)
        gate = cycles.gate(cycleId)
        if gate.cycle.communityId != actor.community_id:
            raise ServiceError("NOT_FOUND")
        with repository.transaction() as state:
            data = state.records.get("formations", {}).get(cycleId)
            if not data:
                raise ServiceError("NOT_FOUND")
            debug = (data["privateFormation"] or {}).get("debug") or {}
        if not debug:
            raise ServiceError("NOT_FOUND")
        # Operator-only: player ids (synthetic in the demo), never answer text.
        return {
            "label": "Keyword grouping next to Muse grouping. Synthetic players.",
            "keywordGroups": debug.get("baselineGroups", []),
            "museGroups": debug.get("museGroups", []),
            "splitByKeywords": debug.get("splitByBaseline", []),
            "agreements": debug.get("agreements", 0),
            "fallbackGrouping": bool(debug.get("usedFallback")),
        }

    # Demo stage: opt-in slots for two players and the operator's big-screen view.
    stage_router, holder["stage_note"] = build_stage_router(
        repository=repository,
        privacy=privacy,
        privacy_store=privacy_store,
        answers=answers,
        cycles=cycles,
        guard=guard,
        calls=calls,
    )
    matching.routes.extend(stage_router.routes)

    def sky_refresh(room_id, tasks):
        job_id = runtime.request_sky_for_room(room_id)
        if job_id is not None:
            tasks.add_task(runtime.run_job, job_id)

    from server.app.v3_routes import build_v3_router

    # Re-register the v3 handlers as plain routes: the registry accepts only direct HTTP routes.
    for route in build_v3_router(
        answers=answers,
        cycles=cycles,
        privacy_actor=privacy,
        muse=KeywordMusePort(muse),
        guard=guard,
        store=v3_store,
    ).routes:
        matching.routes.append(route)

    nudges = GuardedNudges(runtime, chat, muse, VERIFIED_TOKEN.get)
    planning = PlanningRuntime(
        questions=questions,
        nudges=nudges,
        venues=nudges.venues,
        room_constellation=nudges.room_constellation,
        muse_configured=muse.configured,
    )
    registrations = [
        ServiceRegistration(
            "privacy",
            privacy_router(privacy, answers, moderation, chat.resolve_handle),
            authorize,
            privacy_ready,
        ),
        ServiceRegistration("cycle", cycle, authorize, storage_ready),
        ServiceRegistration("voice", voice, authorize, voice_ready),
        ServiceRegistration("matching", matching, authorize, model_ready),
        ServiceRegistration(
            "planning", planning_router(planning, authorize), authorize, planning.ready
        ),
        ServiceRegistration("orchestration", orchestrator, authorize, storage_ready),
        ServiceRegistration(
            "chat", chat_router(chat, authorize, sky_refresh=sky_refresh), authorize, storage_ready
        ),
    ]
    app = create_app(settings=settings, registrations=registrations)
    install_privacy_error_handler(app)
    install_cycle_error_handler(app)
    install_planning_error_handler(app)
    app.state.runtime, app.state.chat, app.state.cycles = runtime, chat, cycles
    app.state.nudges = nudges
    app.state.v3_store, app.state.v3_scheduler = v3_store, v3_scheduler
    app.state.privacy, app.state.answers, app.state.muse = privacy, answers, muse
    previous = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous(application):
            holder["loop"] = asyncio.get_running_loop()
            worker = asyncio.create_task(runtime.loop(chat)) if start_worker else None
            try:
                yield
            finally:
                if worker:
                    worker.cancel()
                    await asyncio.gather(worker, return_exceptions=True)

    app.router.lifespan_context = lifespan
    return app
