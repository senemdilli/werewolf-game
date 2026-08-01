from wolf_llm_labeling.contexts import (
    ContextProvider,
    JoinedContext,
    StaticContext,
    GameNowContext,
    PhaseGameContext,
    PhaseTrustContext,
    InnerTrustVoiceContext,
)
from wolf_llm_labeling.inner_voice import InnerVoice, LLMInnerVoice, HumanHistoricInnerVoice, RandomInnerVoice
from wolf_llm_labeling.models import PlayerName, LLMModelProviders


def experiment(
    player_name: PlayerName,
    args: str,
    models: LLMModelProviders,
) -> tuple[ContextProvider, InnerVoice | None]:
    parts = args.strip().split()
    cutoff = int(parts[0]) if len(parts) > 0 else 0
    variant = int(parts[1]) if len(parts) > 1 else 2
    iv_type = parts[2] if len(parts) > 2 else "llm"
    
    if iv_type == "human":
        inner_voice = HumanHistoricInnerVoice(player_name)
    elif iv_type == "random":
        inner_voice = RandomInnerVoice()
    else:
        inner_voice = LLMInnerVoice()
    
    # Base context: Game static + Game now
    base_ctx = JoinedContext('Game Information', None, 1000, StaticContext(player_name), GameNowContext(player_name))
    
    # Historical phases: game data and trust scores
    game_history = [PhaseGameContext(i) for i in range(1, cutoff)]
    trust_history = [PhaseTrustContext(i, player_name=player_name) for i in range(1, cutoff)]
    
    history_elements = game_history + trust_history
    
    if history_elements:
        history_ctx = JoinedContext('Historical Game History', None, 0, *history_elements)
        ctx = JoinedContext(None, None, 0, base_ctx, PhaseGameContext(0), history_ctx)
    else:
        ctx = JoinedContext(None, None, 0, base_ctx, PhaseGameContext(0))
        
    if variant == 1:
        iv_ctx = InnerTrustVoiceContext(inner_voice, ctx)
        ctx_with_iv = JoinedContext(None, None, 0, ctx, iv_ctx)
        return (ctx_with_iv, None)
    else:
        return (ctx, inner_voice)
