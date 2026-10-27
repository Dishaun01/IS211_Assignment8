"""Deterministic checks of Pig rules, factory selection, and deadlines."""

import contextlib
import io
import time
import unittest
from unittest.mock import patch

from pig import (ComputerPlayer, Game, HumanPlayer, Player,
                 PlayerFactory, TimedGameProxy, TimeExpired)


class FixedDie:
    def __init__(self, rolls):
        self.rolls = iter(rolls)

    def roll(self):
        return next(self.rolls)


class PigTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_factory_and_inheritance(self):
        self.assertIsInstance(PlayerFactory.create_player("human", "H"), HumanPlayer)
        self.assertIsInstance(PlayerFactory.create_player("computer", "C"), ComputerPlayer)
        self.assertIsInstance(ComputerPlayer("C"), Player)
        with self.assertRaises(ValueError):
            PlayerFactory.create_player("unknown", "X")

    def test_computer_thresholds(self):
        player = ComputerPlayer("C")
        for score, threshold in [(0, 25), (74, 25), (80, 20), (99, 1)]:
            player.score = score
            self.assertEqual(player.choose_action(threshold - 1, None), "roll")
            self.assertEqual(player.choose_action(threshold, None), "hold")

    def test_roll_one_loses_only_turn_points(self):
        game = Game("computer", "computer", FixedDie([6, 1]))
        game.players[0].score = 10
        game.play_turn()
        self.assertEqual(game.players[0].score, 10)

    def test_hold_banks_points(self):
        game = Game("computer", "computer", FixedDie([6, 6, 6, 6, 6]))
        game.play_turn()
        self.assertEqual(game.players[0].score, 30)

    def test_human_invalid_input_then_hold(self):
        game = Game(die=FixedDie([5]))
        answers = iter(["invalid", "r", "h"])
        game.play_turn(lambda prompt: next(answers))
        self.assertEqual(game.players[0].score, 5)

    def test_full_game_switches_turns_and_reaches_100(self):
        game = Game("computer", "computer", FixedDie([6] * 100))
        winner = game.play()
        self.assertIs(winner, game.players[0])
        self.assertEqual(winner.score, 102)
        self.assertEqual(game.players[1].score, 90)

    def test_deadline_boundary(self):
        now = [100]
        proxy = TimedGameProxy(Game(), clock=lambda: now[0])
        proxy.started_at = 100
        now[0] = 159.999
        proxy.check_time()
        now[0] = 160
        with self.assertRaises(TimeExpired):
            proxy.check_time()

    def test_timeout_selects_banked_leader_and_discards_turn(self):
        game = Game()
        game.players[1].score = 12
        proxy = TimedGameProxy(game, clock=lambda: 0)

        def late_answer(prompt):
            raise TimeExpired

        self.assertIs(proxy.play(read_input=late_answer), game.players[1])
        self.assertTrue(proxy.timed_out)
        self.assertEqual(game.players[0].score, 0)

    def test_timeout_tie(self):
        proxy = TimedGameProxy(Game(), duration=0)
        self.assertIsNone(proxy.play())
        self.assertTrue(proxy.timed_out)

    def test_waiting_for_human_input_expires(self):
        proxy = TimedGameProxy(Game(), duration=0.03)
        with patch("builtins.input", side_effect=lambda prompt: time.sleep(0.2)):
            start = time.monotonic()
            proxy.play()
            elapsed = time.monotonic() - start
        self.assertTrue(proxy.timed_out)
        self.assertLess(elapsed, 0.15)

    def test_timed_game_can_finish_before_deadline(self):
        game = Game("computer", "computer", FixedDie([6] * 100))
        proxy = TimedGameProxy(game, clock=lambda: 0)
        self.assertIs(proxy.play(), game.players[0])
        self.assertFalse(proxy.timed_out)


if __name__ == "__main__":
    unittest.main()
