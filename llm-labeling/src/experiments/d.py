from wolf_llm_labeling.contexts import (
    ContextProvider,
    JoinedContext,
    StaticContext,
    GameNowContext,
    PhaseGameContext,
    InnerTrustVoiceContext,
)
from wolf_llm_labeling.inner_voice import InnerVoice, AskMyselfInnerVoice
from wolf_llm_labeling.models import PlayerName, LLMModelProviders


def experiment(
    player_name: PlayerName,
    args: str,
    models: LLMModelProviders,
) -> tuple[ContextProvider, InnerVoice | None]:
    parts = args.strip().split()
    cutoff = int(parts[0]) if len(parts) > 0 else 0
    variant = int(parts[1]) if len(parts) > 1 else 2
    
    inner_voice = AskMyselfInnerVoice()
    
    # Base context: Game static + Game now
    base_ctx = JoinedContext('Game Information', None, 1000, StaticContext(player_name), GameNowContext(player_name))
    
    # Historical phases: game data only (excluding trust scores)
    game_history = [PhaseGameContext(i) for i in range(1, cutoff)]
    
    if game_history:
        history_ctx = JoinedContext('Historical Game History', None, 0, *game_history)
        ctx = JoinedContext(None, None, 0, base_ctx, PhaseGameContext(0), history_ctx)
    else:
        ctx = JoinedContext(None, None, 0, base_ctx, PhaseGameContext(0))
        
    if variant == 1:
        # Variant 1: put result of the inner trust voice directly into context
        iv_ctx = InnerTrustVoiceContext(inner_voice, ctx)
        ctx_with_iv = JoinedContext(None, None, 0, ctx, iv_ctx)
        return (ctx_with_iv, None)
    else:
        # Variant 2: agentic loop where LLM can call it as a tool
        return (ctx, inner_voice)
