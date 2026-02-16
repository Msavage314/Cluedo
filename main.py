from rich import print
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
import dataclasses
import copy
import itertools


console = Console(highlight=False)


@dataclasses.dataclass
class Suggestion:
    weapon: str
    suspect: str
    location: str

    @property
    def cards(self):
        s = set()
        s.add(self.weapon)
        s.add(self.suspect)
        s.add(self.location)
        return s


@dataclasses.dataclass
class CluedoConfiguration:
    weapons: list[str]
    suspects: list[str]
    locations: list[str]

    @property
    def cards(self):
        return self.suspects + self.locations + self.weapons


STANDARD = CluedoConfiguration(
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


class Player:
    def __init__(self, name, position, config: CluedoConfiguration):
        self.cards = set()
        self.not_cards = set()
        self.position = position
        self.name = name
        self.config = config

    def __str__(self) -> str:
        return str(self.cards)

    def add_card(self, card):
        if card not in self.config.cards:
            raise ValueError("Not a valid card")
        self.cards.add(card)

    def mark_not_card(self, card):
        if card not in self.cards:
            self.not_cards.add(card)

    def has_card(self, card: str) -> bool:
        """Check if player has a specific card"""
        return card in self.cards

    def might_have_card(self, card: str) -> bool:
        """Check if player might have this card (unknown)"""
        return card not in self.cards and card not in self.not_cards

    def can_show_any(self, suggestion: Suggestion):
        return any(card in self.cards for card in suggestion.cards)


class CluedoSolver:
    def __init__(self):
        console.clear()
        console.print("Loading Cluedo solver...")
        configuration = Prompt.ask(
            "Select configuration", choices=["standard", "harry potter"]
        )
        match configuration:
            case "harry potter":
                self.config = HARRY_POTTER
                self.weapons = HARRY_POTTER.weapons
                self.suspects = HARRY_POTTER.suspects
                self.locations = HARRY_POTTER.locations
            case _:
                self.config = STANDARD
                self.weapons = STANDARD.weapons
                self.suspects = STANDARD.suspects
                self.locations = STANDARD.locations

        console.print(f"[bold green]Selected {configuration} successfully[/]")

        self.num_players = IntPrompt.ask(
            "Number of players",
        )
        self.players: list[Player] = []

        for i in range(self.num_players):
            name = Prompt.ask("Enter player name")
            p = Player(name, i, self.config)
            self.players.append(p)

        console.print(f"[bold green]Initialised {self.num_players} players![/]")

        console.print()
        self.unknown_cards = set(self.config.cards)
        self.solution_possibilities = {
            "suspect": set(self.suspects),
            "weapon": set(self.weapons),
            "location": set(self.locations),
        }

        your_name = Prompt.ask(
            "What is your name?", choices=[p.name for p in self.players]
        )
        self.your_name = your_name
        self.your_position = next(
            i for i, p in enumerate(self.players) if p.name == your_name
        )

        cards_each = int((len(self.config.cards) - 3) // self.num_players)
        # Bonus cards left over (everyone sees)
        bonus = int((len(self.config.cards) - 3) % self.num_players)
        total_cards_each = cards_each + bonus
        console.line()
        console.print(
            f"[yellow]You should have {total_cards_each} cards: {cards_each} cards each plus {bonus} bonus cards in the middle[/]"
        )
        console.line()
        for i in range(total_cards_each):
            # Only show cards that haven't been selected yet
            available_cards = [
                c
                for c in self.config.cards
                if c not in self.players[self.your_position].cards
            ]
            c = Prompt.ask(f"Enter card {i + 1}", choices=available_cards)
            self.add_player_card(self.your_position, c)
            console.line()

        console.print(
            f"[bold green]Setup complete! You have: {self.players[self.your_position].cards}[/]"
        )

        for i in itertools.cycle(range(self.num_players)):
            self.take_turn(i)

    def take_turn(self, player_index: int):
        player = self.players[player_index]
        console.print(f"{player.name}s turn...")
        if Confirm.ask(f"Did {player.name} ask anything"):
            suspect = Prompt.ask("Enter suspect", choices=self.config.suspects)
            weapon = Prompt.ask("Enter weapon", choices=self.config.weapons)
            room = Prompt.ask("Enter room", choices=self.config.locations)
            s = Suggestion(weapon, suspect, room)
            answer_index = (player_index + 1) % self.num_players
            doesnt_have = 0
            for _ in range(self.num_players - 1):
                player = self.players[answer_index]
                if player.name == self.your_name:
                    console.print("Your turn:")
                    overlapping_cards = s.cards & player.cards
                    if overlapping_cards:
                        console.print("You could show one of the following cards")
                        for card in overlapping_cards:
                            print(card)

                if not Confirm.ask(f"Did {player.name} show anything? "):
                    # TODO implement logic here
                    doesnt_have += 1

                answer_index = (answer_index + 1) % self.num_players
            # all players said no
            if doesnt_have == self.num_players - 1:
                cards = s.cards.difference(player.cards)
                for card in cards:
                    self.solution_possibilities[self.get_card_type(card)] = set([card])

        self.print_status()

    def add_player_card(self, player_index: int, card: str):
        player = self.players[player_index]

        player.add_card(card)

        self.unknown_cards.discard(card)

        for i in range(self.num_players):
            if i != player_index:
                self.players[i].mark_not_card(card)

        card_type = self.get_card_type(card)
        if card_type:
            self.solution_possibilities[card_type].discard(card)

    def get_unknown_cards(self):
        """Get list of cards that are still unknown"""
        return sorted(list(self.unknown_cards))

    def mark_card_not_owned(self, player_position: int, card: str):
        self.players[player_position].mark_not_card(card)

    def get_card_type(self, card: str):
        """Determine if card is suspect, weapon, or location"""
        if card in self.suspects:
            return "suspect"
        elif card in self.weapons:
            return "weapon"
        elif card in self.locations:
            return "location"
        else:
            raise ValueError("Invalid card type")

    def print_status(self):
        console.print("\n[bold] =====Game [bold]Status=====[/]")
        console.print(
            f"\n[yellow]Unknown cards ({len(self.unknown_cards)}):[/] {self.get_unknown_cards()}"
        )

        console.print("\n[bold]Solution Possibilities:[/]")
        for card_type in ["suspect", "weapon", "location"]:
            possible = sorted(list(self.solution_possibilities[card_type]))
            console.print(f"{card_type.capitalize()}: {possible}")

        solution = self.get_solution()
        if all(solution.values()):
            console.print(
                f"\n[bold green] SOLUTION: {solution['suspect']} with {solution['weapon']} in {solution['location']}[/]"
            )
            exit()

    def get_solution(self):
        """Return the deduced solution (or None for unknown parts)"""
        solution = {}
        for card_type in ["suspect", "weapon", "location"]:
            possible = list(self.solution_possibilities[card_type])
            solution[card_type] = possible[0] if len(possible) == 1 else None
        return solution


if __name__ == "__main__":
    c = CluedoSolver()
