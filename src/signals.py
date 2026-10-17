from src import constants
from src.card_logic import get_card_colors


class SignalCalculator:
    def __init__(self, set_metrics, color_ratings=None):
        self.metrics = set_metrics
        from math import isfinite

        self.pair_baselines = {}
        for pair, rate in (color_ratings or {}).items():
            if (isinstance(pair, str) and len(pair) == 2
                    and set(pair) <= set("WUBRG") and len(set(pair)) == 2
                    and isinstance(rate, (int, float)) and isfinite(rate)
                    and 0 < rate <= 100):
                self.pair_baselines[frozenset(pair)] = rate
        # Get the global average win rate for "All Decks" to use as a baseline
        self.baseline_wr, _ = self.metrics.get_metrics(
            constants.FILTER_OPTION_ALL_DECKS, constants.DATA_FIELD_GIHWR
        )

        # Fallback if metrics aren't loaded or valid
        if self.baseline_wr == 0.0:
            self.baseline_wr = 54.0  # A conservative 17Lands average

    def calculate_pack_signals(self, pack_cards, current_pick):
        """
        Scans a list of cards and calculates signal scores for each color.
        Signal Score = (Lateness) * (Quality vs Baseline)
        """
        # Initialize scores: W, U, B, R, G
        color_signals = {c: 0.0 for c in constants.CARD_COLORS}

        for card in pack_cards:
            try:
                # 1. Get Stats from "All Decks" bucket
                deck_stats = card.get(constants.DATA_FIELD_DECK_COLORS, {}).get(
                    constants.FILTER_OPTION_ALL_DECKS, {}
                )
                gihwr = deck_stats.get(constants.DATA_FIELD_GIHWR, 0.0)
                ata = deck_stats.get(constants.DATA_FIELD_ATA, 0.0)

                # 2. Data Validation
                if gihwr == 0.0 or ata == 0.0:
                    continue

                # 3. Quality Filter
                # If a card has a win rate below the set average, seeing it late is not a signal
                if gihwr <= self.baseline_wr:
                    continue

                # 4. Lateness Calculation
                lateness = current_pick - ata

                if lateness <= 0:
                    continue

                # 5. Score Calculation
                quality_diff = gihwr - self.baseline_wr
                card_score = lateness * quality_diff

                # 6. Color Attribution
                card_colors = card.get(constants.DATA_FIELD_COLORS, [])

                # Handle colorless cards with colored mana costs
                if not card_colors and constants.DATA_FIELD_MANA_COST in card:
                    mana_colors = get_card_colors(card[constants.DATA_FIELD_MANA_COST])
                    card_colors = list(mana_colors.keys())

                # Distribute score to each color
                for color in card_colors:
                    if color in color_signals:
                        color_signals[color] += card_score

            except Exception:
                continue

        return color_signals


    PAIRS = ("WU", "UB", "BR", "RG", "WG", "WB", "UR", "BG", "WR", "UG")

    def calculate_pack_pair_signals(self, pack_cards, current_pick, card_stats=None):
        """Sum positive lateness * pair quality, in percentage-point units.

        Each pair uses its deck win rate as baseline, falling back to the set mean.
        LLU rates are fractions; dataset rates and the baseline are percentages.
        Missing LLU values fall back to the corresponding 17Lands pair bucket.
        Pair performance includes cards splashed into that pair, like the source data.
        """
        from math import isfinite

        scores = dict.fromkeys(self.PAIRS, 0.0)
        card_stats = card_stats or {}
        for card in pack_cards:
            stats = card_stats.get(card.get(constants.DATA_FIELD_NAME), {})
            buckets = card.get(constants.DATA_FIELD_DECK_COLORS, {})
            ata = stats.get("ata")
            if ata is None:
                ata = buckets.get(constants.FILTER_OPTION_ALL_DECKS, {}).get(
                    constants.DATA_FIELD_ATA, 0.0
                )
            if not isinstance(ata, (int, float)) or not isfinite(ata) or ata <= 0:
                continue
            lateness = current_pick - ata
            if lateness <= 0:
                continue
            for pair in self.PAIRS:
                rate = stats.get("pairs", {}).get(pair, {}).get("gihWr")
                if rate is not None:
                    rate = rate * 100 if isinstance(rate, (int, float)) else None
                else:
                    bucket = next((value for key, value in buckets.items()
                                   if len(key) == 2 and set(key) == set(pair)), {})
                    rate = bucket.get(constants.DATA_FIELD_GIHWR)
                if not isinstance(rate, (int, float)) or not isfinite(rate):
                    continue
                baseline = self.pair_baselines.get(frozenset(pair), self.baseline_wr)
                if baseline < rate <= 100:
                    scores[pair] += lateness * (rate - baseline)
        return scores
