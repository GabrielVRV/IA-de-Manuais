from datetime import timedelta

import pytest

from manual_assistant.application.errors import ConversationNotFoundError, ExternalServiceError
from manual_assistant.application.use_cases.ask_question import AskQuestionUseCase
from manual_assistant.application.use_cases.conversations import (
    CONTEXT_EXCHANGES,
    ChatUseCase,
    DeleteConversationUseCase,
    GetConversationUseCase,
    ListConversationsUseCase,
    PurgeIdleConversationsUseCase,
    RenameConversationUseCase,
)
from manual_assistant.domain.chunk import ScoredChunk
from manual_assistant.domain.conversation import ConversationId, RetentionPolicy
from manual_assistant.domain.pages import PageRange
from manual_assistant.domain.question import Question
from manual_assistant.domain.user import User
from tests.factories import FIXED_NOW, make_chunk, make_manual
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLanguageModel,
    InMemoryConversationRepository,
    InMemoryVectorStore,
)
from tests.security import make_user

pytestmark = pytest.mark.anyio

manual = make_manual("Manual da Prensa P-200")


class Context:
    def __init__(self) -> None:
        self.now = FIXED_NOW
        self.conversations = InMemoryConversationRepository()
        self.embeddings = FakeEmbeddingProvider()
        self.language_model = FakeLanguageModel(answer="A pressão máxima é 180 bar [1].")
        self.chat = ChatUseCase(
            conversations=self.conversations,
            ask_question=AskQuestionUseCase(
                embeddings=self.embeddings,
                vector_store=InMemoryVectorStore(
                    search_results=[
                        ScoredChunk(
                            make_chunk(manual, text="Pressão: 180 bar.", pages=PageRange(12, 12)),
                            0.9,
                        )
                    ]
                ),
                language_model=self.language_model,
            ),
            clock=lambda: self.now,
        )
        self.maria = make_user("maria")
        self.joao = make_user("joao")

    async def ask(
        self, question: str, conversation_id: ConversationId | None = None, *, as_: User
    ) -> ConversationId:
        reply = await self.chat.execute(as_, Question(question), conversation_id)
        return reply.conversation.id


class TestChat:
    async def test_first_question_starts_a_titled_conversation_and_saves_the_answer(
        self,
    ) -> None:
        ctx = Context()

        reply = await ctx.chat.execute(ctx.maria, Question("Qual a pressão máxima?"))

        assert reply.conversation.title == "Qual a pressão máxima?"
        assert reply.exchange.answer.text == "A pressão máxima é 180 bar."
        stored = await ctx.conversations.get(reply.conversation.id)
        assert stored is not None
        assert stored.owner_id == ctx.maria.id
        assert [e.question for e in stored.exchanges] == ["Qual a pressão máxima?"]

    async def test_follow_up_goes_to_the_same_conversation_with_the_previous_context(
        self,
    ) -> None:
        ctx = Context()
        conversation_id = await ctx.ask("Qual a pressão máxima da P-200?", as_=ctx.maria)
        ctx.now += timedelta(minutes=2)

        await ctx.ask("E a mínima?", conversation_id, as_=ctx.maria)

        stored = await ctx.conversations.get(conversation_id)
        assert stored is not None
        assert [e.question for e in stored.exchanges] == [
            "Qual a pressão máxima da P-200?",
            "E a mínima?",
        ]
        assert stored.updated_at == ctx.now
        follow_up_prompt = ctx.language_model.requests[-1].prompt
        assert "<pergunta>Qual a pressão máxima da P-200?</pergunta>" in follow_up_prompt

    async def test_only_the_last_exchanges_go_as_context(self) -> None:
        ctx = Context()
        conversation_id = await ctx.ask("Pergunta 0", as_=ctx.maria)
        for n in range(1, CONTEXT_EXCHANGES + 2):
            await ctx.ask(f"Pergunta {n}", conversation_id, as_=ctx.maria)

        prompt = ctx.language_model.requests[-1].prompt

        assert prompt.count("<pergunta>") == CONTEXT_EXCHANGES
        assert "<pergunta>Pergunta 0</pergunta>" not in prompt

    async def test_saves_nothing_when_the_answer_fails(self) -> None:
        ctx = Context()
        ctx.language_model.error = ExternalServiceError("IA fora do ar")

        with pytest.raises(ExternalServiceError):
            await ctx.ask("Qual a pressão máxima?", as_=ctx.maria)

        assert ctx.conversations.conversations == {}

    async def test_cannot_continue_someone_elses_conversation(self) -> None:
        ctx = Context()
        conversation_id = await ctx.ask("Qual a pressão máxima?", as_=ctx.maria)

        with pytest.raises(ConversationNotFoundError):
            await ctx.ask("E a mínima?", conversation_id, as_=ctx.joao)


class TestHistory:
    async def test_lists_only_the_users_conversations_most_recent_first(self) -> None:
        ctx = Context()
        first = await ctx.ask("Qual a pressão máxima?", as_=ctx.maria)
        ctx.now += timedelta(hours=1)
        second = await ctx.ask("Como trocar o óleo?", as_=ctx.maria)
        await ctx.ask("Pergunta do João", as_=ctx.joao)

        summaries = await ListConversationsUseCase(ctx.conversations).execute(ctx.maria)

        assert [s.id for s in summaries] == [second, first]
        assert summaries[0].exchange_count == 1

    async def test_owner_reads_renames_and_deletes(self) -> None:
        ctx = Context()
        conversation_id = await ctx.ask("Qual a pressão máxima?", as_=ctx.maria)

        renamed = await RenameConversationUseCase(ctx.conversations).execute(
            ctx.maria, conversation_id, "Pressão da P-200"
        )
        opened = await GetConversationUseCase(ctx.conversations).execute(ctx.maria, conversation_id)
        await DeleteConversationUseCase(ctx.conversations).execute(ctx.maria, conversation_id)

        assert renamed.title == opened.title == "Pressão da P-200"
        assert await ctx.conversations.get(conversation_id) is None

    async def test_others_cannot_read_rename_or_delete(self) -> None:
        ctx = Context()
        conversation_id = await ctx.ask("Qual a pressão máxima?", as_=ctx.maria)

        with pytest.raises(ConversationNotFoundError):
            await GetConversationUseCase(ctx.conversations).execute(ctx.joao, conversation_id)
        with pytest.raises(ConversationNotFoundError):
            await RenameConversationUseCase(ctx.conversations).execute(
                ctx.joao, conversation_id, "Minha agora"
            )
        with pytest.raises(ConversationNotFoundError):
            await DeleteConversationUseCase(ctx.conversations).execute(ctx.joao, conversation_id)
        assert await ctx.conversations.get(conversation_id) is not None


class TestRetention:
    async def test_deletes_only_conversations_idle_beyond_the_limit(self) -> None:
        ctx = Context()
        ctx.now = FIXED_NOW - timedelta(days=91)
        old = await ctx.ask("Pergunta antiga", as_=ctx.maria)
        ctx.now = FIXED_NOW - timedelta(days=10)
        recent = await ctx.ask("Pergunta recente", as_=ctx.maria)
        purge = PurgeIdleConversationsUseCase(
            ctx.conversations, RetentionPolicy(timedelta(days=90)), clock=lambda: FIXED_NOW
        )

        assert await purge.execute() == 1
        assert await ctx.conversations.get(old) is None
        assert await ctx.conversations.get(recent) is not None

    async def test_keeps_everything_without_a_limit(self) -> None:
        ctx = Context()
        ctx.now = FIXED_NOW - timedelta(days=900)
        await ctx.ask("Pergunta antiga", as_=ctx.maria)
        purge = PurgeIdleConversationsUseCase(
            ctx.conversations, RetentionPolicy(None), clock=lambda: FIXED_NOW
        )

        assert await purge.execute() == 0
        assert len(ctx.conversations.conversations) == 1
