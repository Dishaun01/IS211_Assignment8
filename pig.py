"""Week 8: Pig using a player factory and a timed game proxy."""

import argparse
import queue
import random
import threading
import time


class TimeExpired(Exception):
    """The timed game's deadline has been reached."""


class Player:
    """Base class shared by human and computer players."""

    def __init__(self, name):
        self.name = name
        self.score = 0

    def choose_action(self, turn_total, read_input):
        raise NotImplementedError


class HumanPlayer(Player):
    def choose_action(self, turn_total, read_input):
        while True:
            action = read_input("Roll or hold? [r/h]: ").strip().lower()
            if action in ("r", "roll"):
                return "roll"
            if action in ("h", "hold"):
                return "hold"
            print("Please enter r or h.")


class ComputerPlayer(Player):
    def choose_action(self, turn_total, read_input):
        threshold = min(25, 100 - self.score)
        return "hold" if turn_total >= threshold else "roll"


class PlayerFactory:
    @staticmethod
    def create_player(player_type, name):
        if player_type == "human":
            return HumanPlayer(name)
        if player_type == "computer":
            return ComputerPlayer(name)
        raise ValueError("Player type must be human or computer.")


class Die:
    def roll(self):
        return random.randint(1, 6)


class Game:
    """Two-player Pig. Only held points count toward a player's score."""

    def __init__(self, player1="human", player2="human", die=None):
        self.players = [
            PlayerFactory.create_player(player1, "Player 1"),
            PlayerFactory.create_player(player2, "Player 2"),
        ]
        self.die = die if die is not None else Die()
        self.current_player = 0

    def play_turn(self, read_input=input, check_time=lambda: None):
        player = self.players[self.current_player]
        turn_total = 0
        check_time()
        print(f"\n{player.name}'s turn. Banked score: {player.score}")
        while True:
            check_time()
            action = player.choose_action(turn_total, read_input)
            check_time()
            if action == "hold":
                player.score += turn_total
                print(f"{player.name} holds. Score: {player.score}")
                return
            result = self.die.roll()
            check_time()
            print(f"{player.name} rolled {result}.")
            if result == 1:
                print("Pig! No points banked this turn.")
                return
            turn_total += result
            print(f"Turn total: {turn_total}")

    def get_winner(self, timed_out=False):
        if timed_out:
            high_score = max(player.score for player in self.players)
            leaders = [p for p in self.players if p.score == high_score]
            return leaders[0] if len(leaders) == 1 else None
        return next((p for p in self.players if p.score >= 100), None)

    def play(self, read_input=input, check_time=lambda: None):
        while self.get_winner() is None:
            check_time()
            self.play_turn(read_input, check_time)
            check_time()
            if self.get_winner() is None:
                self.current_player = 1 - self.current_player
        self.announce_result()
        return self.get_winner()

    def announce_result(self, timed_out=False):
        print("\nFinal scores:")
        for player in self.players:
            print(f"{player.name}: {player.score}")
        winner = self.get_winner(timed_out)
        print(f"{winner.name} wins!" if winner else "The game is a tie!")


class TimedGameProxy:
    """Wrap Game and enforce a 60-second deadline using a monotonic clock."""

    def __init__(self, game, duration=60, clock=time.monotonic):
        self.game = game
        self.duration = duration
        self.clock = clock
        self.started_at = None
        self.timed_out = False

    def __getattr__(self, name):
        # Preserve access to the wrapped Game's attributes and methods.
        return getattr(self.game, name)

    def check_time(self):
        if self.started_at is not None:
            if self.clock() - self.started_at >= self.duration:
                raise TimeExpired

    def read_input(self, prompt):
        """A daemon input reader lets the deadline expire on Windows too."""
        self.check_time()
        answers = queue.Queue()

        def read():
            try:
                answers.put((True, input(prompt)))
            except Exception as error:
                answers.put((False, error))

        threading.Thread(target=read, daemon=True).start()
        remaining = self.duration - (self.clock() - self.started_at)
        try:
            success, answer = answers.get(timeout=max(0, remaining))
        except queue.Empty:
            raise TimeExpired from None
        self.check_time()
        if not success:
            raise answer
        return answer

    def play_turn(self, read_input=None, check_time=None):
        return self.game.play_turn(
            self.read_input if read_input is None else read_input,
            self.check_time if check_time is None else check_time,
        )

    def get_winner(self, timed_out=None):
        return self.game.get_winner(
            self.timed_out if timed_out is None else timed_out
        )

    def announce_result(self, timed_out=None):
        self.game.announce_result(
            self.timed_out if timed_out is None else timed_out
        )

    def play(self, read_input=None, check_time=None):
        self.started_at = self.clock()
        self.timed_out = False

        def check():
            self.check_time()
            if check_time is not None:
                check_time()

        print(f"Timed Pig: {self.duration} seconds.")
        try:
            return self.game.play(
                self.read_input if read_input is None else read_input, check
            )
        except TimeExpired:
            self.timed_out = True
            print("\nTime is up! Unbanked turn points do not count.")
            self.announce_result()
            return self.get_winner()


def main():
    parser = argparse.ArgumentParser(description="Play Pig with humans or computers.")
    parser.add_argument("--player1", choices=("human", "computer"), default="human")
    parser.add_argument("--player2", choices=("human", "computer"), default="human")
    parser.add_argument("--timed", action="store_true", help="Limit play to one minute")
    args = parser.parse_args()
    game = Game(args.player1, args.player2)
    if args.timed:
        game = TimedGameProxy(game)
    try:
        game.play()
    except (EOFError, KeyboardInterrupt):
        print("\nGame ended by the user.")


if __name__ == "__main__":
    main()
