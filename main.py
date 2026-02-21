"""Provides a solver and implementation for playing the game Cluedo (Clue)

Provides configuration classes, a game implementation, players and multiple versions
"""

from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel
import dataclasses
import itertools
import copy

# Custom console for rich highlighting/precise control
console = Console(highlight=False)


# -----------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------
class CluedoConfiguration:
    """
    Represents a configuration for the Cluedo game, e.g. Harry Potter or Standard
    defines lists of weapons, suspects and locations.
    """

    configs = []

    def __init__(
        self, name: str, weapons: list[str], suspects: list[str], locations: list[str]
    ):
        self.name: str = name
        self.weapons: list[str] = weapons
        self.suspects: list[str] = suspects
        self.locations: list[str] = locations
        CluedoConfiguration.configs.append(self)

    @classmethod
    def get_by_name(cls, name: str) -> CluedoConfiguration:
        for config in cls.configs:
            if config.name == name:
                return config
        raise ValueError(f"Unknown configuration: {name}")

    @classmethod
    def known_configurations(cls) -> list[CluedoConfiguration]:
        """Returns any declared configurations"""
        return cls.configs

    @property
    def cards(self):
        return self.suspects + self.locations + self.weapons


STANDARD = CluedoConfiguration(
    name="Standard",
    weapons=["Candlestick", "Dagger", "Lead Pipe", "Revolver", "Rope", "Wrench"],
    suspects=["Scarlett", "Mustard", "White", "Green", "Peacock", "Plum"],
    locations=[
        "Ballroom",
        "Billiard Room",
        "Conservatory",
        "Dining Room",
        "Hall",
        "Kitchen",
        "Library",
        "Lounge",
        "Study",
    ],
)

HARRY_POTTER = CluedoConfiguration(
    name="Harry Potter",
    weapons=[
        "Stupefy",
        "Incendio",
        "Love Potion",
        "Cursed Necklace",
        "Poisoned Mead",
        "Jinxed Broomstick",
    ],
    suspects=["Fenrir", "Pettigrew", "Bellatrix", "Draco", "Lucius", "Snatcher"],
    locations=[
        "Forest",
        "Hogwarts",
        "Hogs head",
        "Shrieking Shack",
        "Malfoy Mannor",
        "Gringotts",
        "Ministry",
        "Grimmauld Place",
        "Weasleys",
    ],
)
# -----------------------------------------------------------------
# Suggestions
# -----------------------------------------------------------------


@dataclasses.dataclass
class Suggestion:
    """Represents a suggestion that someone could make
    for example 'Rev Green in the Ballroom with the wrench'
    """

    suspect: str
    weapon: str
    location: str

    def __str__(self) -> str:
        return f"{self.suspect} with the {self.weapon} in the {self.location}"

    @property
    def cards(self) -> set[str]:
        s = set()
        s.add(self.weapon)
        s.add(self.suspect)
        s.add(self.location)
        return s


# -----------------------------------------------------------------
# Players
# -----------------------------------------------------------------
class Player:
    names = []

    def __init__(self, name: str, position: int, config: CluedoConfiguration):
        self.name = name
        self.register_name(name)
        self.position = position
        self.config = config
        # set of cards that the player definitely does have
        self.cards = set()
        # set of cards that the player definitely does not have
        self.not_cards = set()

    def __str__(self) -> str:
        return f"Summary of {self.name}\nHand: {self.cards}"

    @classmethod
    def register_name(cls, name):
        cls.names.append(name)

    def add_card(self, card):
        """Attempts to add a card to the players hand. If it is not a valid card, raise ValueError"""
        if card not in self.config.cards:
            raise ValueError("Not a valid card")
        self.cards.add(card)

    def mark_not_card(self, card):
        self.not_cards.add(card)

    def has_card(self, card: str) -> bool:
        """Check if player has a specific card"""
        return card in self.cards

    def might_have_card(self, card: str) -> bool:
        """Check if player might have this card (unknown)"""
        return card not in self.cards and card not in self.not_cards

    def can_show_any(self, suggestion: Suggestion):
        """Check if the player can show any cards for a specific suggestion"""
        return any(card in self.cards for card in suggestion.cards)

    def respond_to_suggestion(self, suggestion: Suggestion) -> str | None: ...


# -----------------------------------------------------------------
# Logic
# -----------------------------------------------------------------
@dataclasses.dataclass
class Constraint:
    """
    Records that a player showed one card from a set, but we don't know which.
    e.g. a player showed one of {Scarlett, Rope, Kitchen}
    """

    player: Player
    possible_cards: frozenset[str]

    def narrow(self) -> Constraint:
        """Return a new constraint with cards the player is known not to have removed."""
        still_possible = frozenset(
            c for c in self.possible_cards if self.player.might_have_card(c)
        )
        return Constraint(self.player, still_possible)

    @property
    def resolved(self) -> bool:
        return len(self.possible_cards) == 1

    @property
    def impossible(self) -> bool:
        return len(self.possible_cards) == 0


class KnowledgeBase:
    """All deduced knowledge about players and the solution"""

    def __init__(self, players: list[Player], config: CluedoConfiguration) -> None:
        self.players = players
        self.possibilities = copy.deepcopy(config)
        self.unknown_cards: set[str] = set(config.cards)
        self.constraints: list[Constraint] = []
        self.solution_possibilities: dict[str, set[str]] = {
            "suspect": set(config.suspects),
            "weapon": set(config.weapons),
            "location": set(config.locations),
        }

    @property
    def num_players(self) -> int:
        return len(self.players)

    def get_card_type(self, card: str) -> str:
        if card in self.possibilities.suspects:
            return "suspect"
        elif card in self.possibilities.weapons:
            return "weapon"
        elif card in self.possibilities.locations:
            return "location"
        raise ValueError(f"Unknown card: {card}")

    def record_has_card(self, player: Player, card: str):
        """Record that a specific player definitely has a card"""
        if card in player.cards:
            return

        player.add_card(card)
        # Cannot be the solution
        self.unknown_cards.discard(card)

        for i, other in enumerate(self.players):
            if other != player:
                other.mark_not_card(card)

        card_type = self.get_card_type(card)
        self.solution_possibilities[card_type].discard(card)

    def record_does_not_have(self, player: Player, card: str):
        """Records that a player does definitely not have a card"""
        player.mark_not_card(card)

    def record_showed_one_of(self, player: Player, possible_cards: set[str]):
        """
        Record that a player showed one card from a set (but we do not know which).
        Immediately resolves if only one card is still possible
        """
        already_known = possible_cards & player.cards

        unknown_subset = frozenset(
            c for c in possible_cards if player.might_have_card(c)
        )
        if len(unknown_subset) == 0:
            pass
        elif len(unknown_subset) == 1:
            # Only one card they could have shown. Must be it
            self.record_has_card(player, next(iter(unknown_subset)))
        else:
            # Save for later!
            self.constraints.append(Constraint(player, unknown_subset))

    def record_no_one_showed(self, suggestion: Suggestion, your_player: Player):
        """
        Nobody showed a card for this suggestion. Any suggested card that isn't in the
        other players hand must be in the solution
        """
        for card in suggestion.cards:
            if card not in your_player.cards:
                card_type = self.get_card_type(card)
                console.print(f"[bold green]{card} must be in the solution![/]")
                self.solution_possibilities[card_type] = {card}
                self.unknown_cards.discard(card)

    def deduce(self) -> bool:
        """
        Runs all detection strategies
        return True if new information was discovered
        """
        overal_changed = False
        changed = True
        while changed:
            changed = False
            changed |= self._deduce_unique_owner()
            changed |= self._deduce_solution_cards()
            changed |= self._propagate_constraints()
            if changed:
                overal_changed = True

        return overal_changed

    def _deduce_unique_owner(self) -> bool:
        """If only one player could possibly hold a card they must have it.
        if no player could have it it must be in the solution
        """
        changed = False
        for card in list(self.unknown_cards):
            possible_owners = [p for p in self.players if p.might_have_card(card)]
            if len(possible_owners) == 1:
                console.print(
                    f"[yellow]Only {possible_owners[0].name} could have {card}![/]"
                )
                self.record_has_card(possible_owners[0], card)
                changed = True
            elif len(possible_owners) == 0:
                # Nobody can have it
                card_type = self.get_card_type(card)
                if len(self.solution_possibilities[card_type]) > 1:
                    console.print(f"[yellow]{card} must be in the solution![/]")
                    self.solution_possibilities[card_type] = {card}
                    self.unknown_cards.discard(card)
                    changed = True
        return changed

    def _deduce_solution_cards(self) -> bool:
        """
        If only one card remains possible for a solution slot, it's confirmed.
        Mark it as not-owned by any player (it's in the envelope).
        """
        changed = False
        for card_type, possible in self.solution_possibilities.items():
            if len(possible) == 1:
                solution_card = next(iter(possible))
                for player in self.players:
                    if player.might_have_card(solution_card):
                        player.mark_not_card(solution_card)
                        changed = True

        return changed

    def _propagate_constraints(self) -> bool:
        """
        Re-evaluate stored constraints in light of new knowledge
        e.g. "player showed one of {A,B,C}". If we ruled out A and B, they must have C

        """
        changed = False
        new_constraints = []
        for constraint in self.constraints:
            narrowed = constraint.narrow()

            if narrowed.impossible:
                console.print(
                    f"[red]Contradiction: {constraint.player.name} should have shown a card",
                    f"from {constraint.possible_cards} but has none of them",
                )
            elif narrowed.resolved:
                card = next(iter(narrowed.possible_cards))
                console.print(
                    f"[yellow]{constraint.player.name} must have {card} (only possibility left)![/]"
                )
                self.record_has_card(constraint.player, card)
                changed = True
            else:
                new_constraints.append(narrowed)

        self.constraints = new_constraints
        return changed

    def get_unknown_cards(self) -> list[str]:
        return sorted(self.unknown_cards)

    @property
    def solution(self) -> dict[str, str | None]:
        return {
            card_type: next(iter(possible)) if len(possible) == 1 else None
            for card_type, possible in self.solution_possibilities.items()
        }

    @property
    def is_solved(self) -> bool:
        return all(v is not None for v in self.solution.values())


class HumanPlayer(Player):
    """The player sitting at the keyboard. Prompts are directed to them."""

    def respond_to_suggestion(self, suggestion: Suggestion) -> str | None:
        """
        Ask the human which card they want to show (if any).
        Returns the card name, or None if they have nothing to show.
        """
        overlapping = suggestion.cards & self.cards
        if not overlapping:
            console.print("[green]You have none of these cards.[/]")
            return None

        console.print(f"[green]You have: {overlapping}[/]")
        if not Confirm.ask("Did you show a card?"):
            return None

        return Prompt.ask(
            prompt="Which card did you show?", choices=sorted(overlapping)
        )


class ObservedPlayer(Player):
    """A player being watched. The human observer is asked what they did."""

    def respond_to_suggestion(self, suggestion: Suggestion) -> str | None:
        """
        Ask the human observer whether this player showed a card.
        Returns None (couldn't show), or a sentinel "unknown" if they showed
        but we don't know which card.
        """
        if Confirm.ask(f"Did {self.name} show a card?"):
            return "unknown"  # They showed something; we don't know what
        return None


class CluedoSolver:
    def __init__(self):
        self.config: CluedoConfiguration = STANDARD
        self.players: list[Player] = []
        self.num_players: int = 4
        self.your_player: HumanPlayer = HumanPlayer("_", 0, self.config)
        self.kb: KnowledgeBase = KnowledgeBase([], STANDARD)

    def run(self):
        """Entry point — set up the game then loop through turns."""
        console.clear()
        console.print("Loading Cluedo solver...")
        self._setup()

        for i in itertools.cycle(range(self.num_players)):
            self._take_turn(i)

    def _setup(self):
        self.config = CluedoConfiguration.get_by_name(
            Prompt.ask(
                "Select configuration",
                choices=[c.name for c in CluedoConfiguration.known_configurations()],
            )
        )
        console.print(f"[bold green]Selected {self.config.name} successfully[/]")

        self.num_players = IntPrompt.ask("Number of players", default=4)
        your_name = Prompt.ask("What is your name?")

        for i in range(self.num_players):
            name = Prompt.ask(f"Enter player {i + 1} name")
            if name == your_name:
                player: Player = HumanPlayer(name, i, self.config)
                self.your_player = player
            else:
                player = ObservedPlayer(name, i, self.config)
            self.players.append(player)

        if self.your_player is None:
            console.print(
                f"[red]'{your_name}' was not in the player list. Defaulting to first player.[/]"
            )
            self.your_player = self.players[0]  # type:ignore[assignment]

        console.print(f"[bold green]Initialised {self.num_players} players![/]")

        self.kb = KnowledgeBase(self.players, self.config)

        cards_each = int((len(self.config.cards) - 3) // self.num_players)
        # Bonus cards left over (everyone sees)
        bonus = int((len(self.config.cards) - 3) % self.num_players)
        total_cards_each = cards_each + bonus

        console.line()
        console.print(
            f"[yellow]You should have {total_cards_each} cards: {cards_each} cards dealt plus {bonus} bonus cards in the middle[/]"
        )
        console.line()
        for i in range(total_cards_each):
            # Only show cards that haven't been selected yet
            available_cards = [
                c for c in self.config.cards if c not in self.your_player.cards
            ]
            card = Prompt.ask(f"Enter card {i + 1}", choices=available_cards)
            self.kb.record_has_card(self.your_player, card)

        console.print(
            f"[bold green]Setup complete! Your hand: {sorted(self.your_player.cards)}[/]"
        )

    def _take_turn(self, player_index: int):
        suggesting_player = self.players[player_index]
        if not Confirm.ask(f"\nDid {suggesting_player.name} make a suggestion"):
            return

        suggestion = self._get_suggestion()
        showed_card = False
        showing_player = None
        shown_card = None

        for answering_player in self._players_after(player_index):
            result = answering_player.respond_to_suggestion(suggestion)
            if result is None:
                for card in suggestion.cards:
                    self.kb.record_does_not_have(answering_player, card)
            elif result == "unknown":
                showed_card = True
                showing_player = answering_player
                break
            else:
                shown_card = result
                showing_player = answering_player

                showed_card = True
                break

        if showed_card and showing_player:
            if shown_card:
                self.kb.record_has_card(showing_player, shown_card)
            else:
                self.kb.record_showed_one_of(showing_player, suggestion.cards)
        else:
            self.kb.record_no_one_showed(suggestion, self.your_player)

        self.kb.deduce()
        self._print_status()

    def _get_suggestion(self) -> Suggestion:
        suspect = Prompt.ask("Please enter the suspect", choices=self.config.suspects)
        weapon = Prompt.ask("Please enter the weapon", choices=self.config.weapons)
        location = Prompt.ask(
            "Please enter the location", choices=self.config.locations
        )
        return Suggestion(suspect, weapon, location)

    def _players_after(self, starting_index: int):
        """Yield players in turn order after the starting player"""
        for i in range(self.num_players - 1):
            yield self.players[(starting_index + 1 + i) % self.num_players]

    def _print_status(self):
        text = ""
        text += f"\n[yellow]Unknown cards ({len(self.kb.unknown_cards)}):[/] {self.kb.get_unknown_cards()}"
        text += "\nSolution Possibilities:"

        for card_type in ["suspect", "weapon", "location"]:
            possible = sorted(self.kb.solution_possibilities[card_type])
            text += f"\n{card_type.capitalize()}: {possible}"

        if self.kb.constraints:
            text += "\nPending Constraints:"
            for c in self.kb.constraints:
                text += f"\n{c.player.name} has one of: {sorted(c.possible_cards)}"

        solution = self.kb.solution
        if self.kb.is_solved:
            text += f"\n[bold green] SOLUTION: {solution['suspect']} with {solution['weapon']} in {solution['location']}[/]"
            panel = Panel(text, title="Game Status")
            console.print(panel)
            exit()
        panel = Panel(text, title="Game Status")
        console.print(panel)


if __name__ == "__main__":
    c = CluedoSolver()
    c.run()
