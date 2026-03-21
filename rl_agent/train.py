"""
Self-play PPO training for the card game.

Requirements:
    pip install gymnasium numpy torch stable-baselines3 sb3-contrib

Self-play loop:
  1. Train current policy against a frozen snapshot of itself.
  2. Every SNAPSHOT_INTERVAL steps, save a checkpoint.
  3. The opponent pool grows over time; each new training run picks the latest
     snapshot as opponent (simple "latest" self-play).

Run:
    python -m rl_agent.train

Optional args (env vars or edit CONF below):
    TOTAL_STEPS=500000
    SNAPSHOT_INTERVAL=50000
    MODEL_DIR=rl_agent/checkpoints
"""
from __future__ import annotations
import os
import copy
import random
import numpy as np

# ---- optional imports checked at runtime -----------------------------------
def _require(pkg, install):
    try:
        return __import__(pkg)
    except ImportError:
        raise ImportError(f"Run: pip install {install}")

# ---- config ----------------------------------------------------------------
CONF = {
    "total_steps":         int(os.getenv("TOTAL_STEPS",         "500000")),
    "snapshot_interval":   int(os.getenv("SNAPSHOT_INTERVAL",   "50000")),
    "model_dir":           os.getenv("MODEL_DIR",
                                     os.path.join(os.path.dirname(__file__), "checkpoints")),
    "n_envs":              4,
    "device":              "auto",
}


# ---- opponent wrapper -------------------------------------------------------

class _SnapshotOpponent:
    """
    A frozen copy of an SB3 policy used as the opponent.
    Plays via action_masks()-aware prediction.
    """
    def __init__(self, model):
        # Deep-copy the policy network weights into a simple callable
        import torch
        self._policy = copy.deepcopy(model.policy)
        self._policy.eval()

    def __call__(self, obs: np.ndarray, mask: np.ndarray) -> int:
        import torch
        with torch.no_grad():
            obs_t  = torch.as_tensor(obs[None], dtype=torch.float32)
            mask_t = torch.as_tensor(mask[None], dtype=torch.bool)
            dist   = self._policy.get_distribution(obs_t)
            logits = dist.distribution.logits[0]
            logits[~mask_t[0]] = -1e9
            return int(torch.argmax(logits).item())


def _random_opponent(obs, mask):
    valid = np.where(mask)[0]
    return int(np.random.choice(valid)) if len(valid) else 1


# ---- build env factory ------------------------------------------------------

def make_env(opponent_policy=None, seed=0):
    """Return a thunk that creates one CardGameEnv."""
    def _thunk():
        from rl_agent.env import CardGameEnv
        env = CardGameEnv(opponent_policy=opponent_policy)
        env.reset(seed=seed)
        return env
    return _thunk


# ---- training ---------------------------------------------------------------

def train(conf: dict = None):
    conf = conf or CONF
    os.makedirs(conf["model_dir"], exist_ok=True)

    # Try MaskablePPO (supports action masks); fall back to regular PPO
    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
        use_masked = True
    except ImportError:
        from stable_baselines3 import PPO as MaskablePPO
        use_masked = False

    from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
    from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback

    total_steps       = conf["total_steps"]
    snapshot_interval = conf["snapshot_interval"]
    n_envs            = conf["n_envs"]

    # Phase 1: train vs random opponent
    print("[train] Phase 1: training vs random opponent")
    current_opponent = _random_opponent

    def _build_vec_env(opp):
        fns = [make_env(opp, seed=i) for i in range(n_envs)]
        return DummyVecEnv(fns)

    vec_env = _build_vec_env(current_opponent)

    if use_masked:
        def mask_fn(env):
            return env.action_masks()

        # Wrap each env with ActionMasker
        from rl_agent.env import CardGameEnv

        def _make_masked(opp, seed):
            def _thunk():
                from sb3_contrib.common.wrappers import ActionMasker
                env = CardGameEnv(opponent_policy=opp)
                env.reset(seed=seed)
                return ActionMasker(env, mask_fn)
            return _thunk

        fns    = [_make_masked(current_opponent, i) for i in range(n_envs)]
        vec_env = DummyVecEnv(fns)
        model  = MaskablePPO("MlpPolicy", vec_env, verbose=1, device=conf["device"])
    else:
        model = MaskablePPO("MlpPolicy", vec_env, verbose=1, device=conf["device"])
        print("[train] WARNING: sb3-contrib not found, training without action masks")
        print("         Install: pip install sb3-contrib")

    # Callback: snapshot + swap opponent
    class _SelfPlayCallback(BaseCallback):
        def __init__(self, interval, model_dir):
            super().__init__()
            self._interval  = interval
            self._model_dir = model_dir
            self._last_snap = 0

        def _on_step(self) -> bool:
            if self.num_timesteps - self._last_snap >= self._interval:
                snap_path = os.path.join(
                    self._model_dir, f"snap_{self.num_timesteps}")
                self.model.save(snap_path)
                print(f"[selfplay] snapshot saved → {snap_path}")
                self._last_snap = self.num_timesteps
                # Update opponent to frozen copy of current policy
                new_opp = _SnapshotOpponent(self.model)
                # Rebuild envs with new opponent
                if use_masked:
                    fns = [_make_masked(new_opp, i) for i in range(n_envs)]
                else:
                    fns = [make_env(new_opp, seed=i) for i in range(n_envs)]
                self.model.set_env(DummyVecEnv(fns))
            return True

    callback = _SelfPlayCallback(snapshot_interval, conf["model_dir"])

    model.learn(total_timesteps=total_steps, callback=callback)

    final_path = os.path.join(conf["model_dir"], "final")
    model.save(final_path)
    print(f"[train] Training complete. Model saved to {final_path}")
    return model


# ---- evaluation -------------------------------------------------------------

def evaluate(model_path: str, n_games: int = 100, verbose: bool = False) -> dict:
    """Load a saved model and evaluate it against a random opponent."""
    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
        use_masked = True
    except ImportError:
        from stable_baselines3 import PPO as MaskablePPO
        use_masked = False

    from rl_agent.env import CardGameEnv

    model = MaskablePPO.load(model_path)

    wins, losses, draws = 0, 0, 0
    total_rounds = 0

    for i in range(n_games):
        env = CardGameEnv(opponent_policy=_random_opponent)
        if use_masked:
            from sb3_contrib.common.wrappers import ActionMasker
            env = ActionMasker(env, lambda e: e.action_masks())

        obs, _ = env.reset(seed=i)
        done = False
        while not done:
            if use_masked:
                action, _ = model.predict(obs, action_masks=env.action_masks())
            else:
                action, _ = model.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated

        w = info.get("winner")
        if w == 0:     wins   += 1
        elif w == 1:   losses += 1
        else:          draws  += 1
        total_rounds += info.get("round", 0)
        if verbose:
            print(f"Game {i+1}: winner={w} rounds={info.get('round')}")

    result = {
        "win_rate":   wins   / n_games,
        "loss_rate":  losses / n_games,
        "draw_rate":  draws  / n_games,
        "avg_rounds": total_rounds / n_games,
        "n_games":    n_games,
    }
    print(f"[eval] Win {result['win_rate']:.1%}  Loss {result['loss_rate']:.1%}  "
          f"Draw {result['draw_rate']:.1%}  avg_rounds={result['avg_rounds']:.1f}")
    return result


# ---- CV calibration stub ----------------------------------------------------

def calibrate_cv(model_path: str, card_pool: list,
                 iterations: int = 50, games_per_iter: int = 200) -> dict:
    """
    Placeholder for CV calibration via win-rate optimisation.

    Strategy:
      1. Vary CV coefficients of each effect by ±δ
      2. Generate random decks weighted by CV for each player
      3. Simulate games with trained policy
      4. Use gradient-free optimisation (e.g. CMA-ES) to minimise |winrate - 0.5|

    This will be implemented once the deck-builder agent is ready.
    """
    raise NotImplementedError(
        "CV calibration requires the deck-builder agent. "
        "Implement deck_builder/optimizer.py first."
    )


# ---- entry point ------------------------------------------------------------

if __name__ == "__main__":
    train()
