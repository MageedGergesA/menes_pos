"""BE-008 tip pooling — the distribution resolver against the frozen contract.

Every case here is taken from ``docs/TIP_POOLING.md`` §2 and its §9 acceptance
paragraph. The invariant the whole module exists for: the distributed total
EQUALS the pool, exactly, for every rule and every set of weights -- a pool that
lands 0.40 LE short is money nobody can account for.

Money is in piastres throughout, so the arithmetic is integer and exact.
"""
import itertools
import random

from odoo.tests import TransactionCase, tagged

from ..domain import tip_pool as tp


def P(key, role='server', minutes=0, captured=0, declared=0):
    return tp.Person(key=key, role=role, minutes=minutes,
                     captured=captured, declared=declared)


@tagged('post_install', '-at_install', 'mezze_tips')
class TestTipPoolResolver(TransactionCase):

    # -- the pool ----------------------------------------------------------
    def test_01_declared_cash_enters_the_pool_under_the_shared_rules(self):
        people = [P('a', captured=1000, declared=500), P('b', captured=0, declared=300)]
        for rule in (tp.EQUAL, tp.HOURS, tp.ROLE, tp.CUSTOM):
            self.assertEqual(tp.pooled_amount(people, rule), 1800,
                             "%s must pool captured + declared" % rule)

    def test_02_declared_cash_stays_with_its_owner_under_direct_and_hybrid(self):
        people = [P('a', captured=1000, declared=500), P('b', captured=0, declared=300)]
        for rule in (tp.DIRECT, tp.HYBRID):
            self.assertEqual(tp.pooled_amount(people, rule), 1000,
                             "%s must not pool declared cash" % rule)

    # -- the acceptance case ----------------------------------------------
    def test_03_hours_worked_splits_pro_rata_and_sums_to_the_pool(self):
        """§9: 6.4 / 5.1 / 3.0 / 2.2 hours, shares sum to the pool exactly."""
        mins = [384, 306, 180, 132]          # 6.4 / 5.1 / 3.0 / 2.2 hours
        people = [P('p%d' % i, minutes=m) for i, m in enumerate(mins)]
        people[0] = people[0]._replace(captured=43000)   # a 430.00 LE pool
        res = tp.distribute(people, tp.HOURS)
        self.assertIsNone(res.err)
        self.assertEqual(res.pool, 43000)
        self.assertEqual(res.total, res.pool, "shares must sum to the pool exactly")
        # pro-rata: the largest share belongs to the longest shift
        self.assertEqual(max(res.rows, key=lambda r: r.share).key, 'p0')
        self.assertEqual([r.key for r in res.rows], ['p0', 'p1', 'p2', 'p3'])

    def test_04_custom_percentages_off_100_refuse_the_run(self):
        """§9: figures totalling 90 -> the run names the shortfall, no shares."""
        people = [P('a', minutes=60), P('b', minutes=60)]
        res = tp.distribute(people, tp.CUSTOM, custom_pct={'a': 60, 'b': 30})
        self.assertEqual(res.err, tp.ERR_CUSTOM_TOTAL)
        self.assertEqual(res.rows, [])
        self.assertEqual(res.total, 0, "a refused run distributes nothing")
        # and exactly 100 is accepted
        ok = tp.distribute(people, tp.CUSTOM, custom_pct={'a': 60, 'b': 40})
        self.assertIsNone(ok.err)
        self.assertEqual(ok.total, ok.pool)

    # -- rounding ----------------------------------------------------------
    def test_05_the_remainder_is_allocated_never_lost(self):
        """1 piastre across 3 equal shares: someone gets it, nobody loses it."""
        people = [P('a'), P('b'), P('c')]
        people[0] = people[0]._replace(captured=100)   # 100 / 3 = 33.33...
        res = tp.distribute(people, tp.EQUAL)
        self.assertEqual(sorted(r.share for r in res.rows), [33, 33, 34])
        self.assertEqual(res.total, 100)

    def test_06_every_rule_conserves_the_pool_over_random_inputs(self):
        """The invariant, fuzzed: no rule may create or destroy a piastre."""
        rnd = random.Random(20260906)
        roles = list(tp.ROLE_WEIGHTS)
        for _ in range(300):
            n = rnd.randint(1, 6)
            people = [P('k%d' % i, role=rnd.choice(roles),
                        minutes=rnd.randint(0, 600),
                        captured=rnd.randint(0, 50000),
                        declared=rnd.randint(0, 20000)) for i in range(n)]
            for rule in (tp.EQUAL, tp.HOURS, tp.ROLE, tp.DIRECT, tp.HYBRID):
                res = tp.distribute(people, rule)
                if res.err:
                    # only ever because there is no weight to split by
                    self.assertEqual(res.err, tp.ERR_NO_WEIGHT)
                    continue
                self.assertEqual(
                    res.total, res.pool,
                    "%s lost or invented money: %s != %s" % (rule, res.total, res.pool))
                self.assertTrue(all(r.share >= 0 for r in res.rows),
                                "no share may be negative")

    # -- the rules ---------------------------------------------------------
    def test_07_role_weights_follow_the_contract(self):
        self.assertEqual(tp.role_weight('Server'), 1.0)
        self.assertEqual(tp.role_weight('bar'), 0.8)
        self.assertEqual(tp.role_weight('kitchen'), 0.5)
        self.assertEqual(tp.role_weight('rider'), 0.5)
        self.assertEqual(tp.role_weight('sommelier'), 1.0,
                         "an unknown tipped role must not silently get nothing")

    def test_07b_every_weighted_role_really_exists_on_a_cashier(self):
        """The weight table and the role vocabulary must not drift apart.

        ROLE_WEIGHTS named 'bar' and 'rider' before mezze.cashier.role offered
        them, so a barperson could not be created at all and, had the selection
        allowed it, would have been paid at a server's weight. A weight for a
        role nobody can hold is a rule that never applies.
        """
        roles = dict(self.env['mezze.cashier']._fields['role'].selection)
        for role in tp.ROLE_WEIGHTS:
            self.assertIn(role, roles,
                          "ROLE_WEIGHTS weighs %r but no cashier can hold it" % role)

    def test_07c_a_weighted_role_carries_capabilities(self):
        """A role that exists but holds nothing is a principal that cannot work."""
        from ..domain import authz
        for role in tp.ROLE_WEIGHTS:
            self.assertTrue(authz.capabilities_for(role),
                            "role %r holds no capabilities" % role)

    def test_08_role_weighted_pays_the_heavier_role_more_for_equal_hours(self):
        people = [P('srv', role='server', minutes=300, captured=10000),
                  P('kit', role='kitchen', minutes=300)]
        res = tp.distribute(people, tp.ROLE)
        by = {r.key: r.share for r in res.rows}
        self.assertGreater(by['srv'], by['kit'])
        self.assertEqual(sum(by.values()), res.pool)

    def test_09_direct_gives_each_server_their_own_captures(self):
        people = [P('a', captured=7000), P('b', captured=3000)]
        res = tp.distribute(people, tp.DIRECT)
        self.assertEqual({r.key: r.share for r in res.rows}, {'a': 7000, 'b': 3000})
        self.assertEqual(res.total, res.pool)

    def test_10_hybrid_tips_out_a_share_of_own_captures(self):
        """A server who captured everything must end up with less than all of it."""
        people = [P('srv', role='server', minutes=300, captured=10000),
                  P('kit', role='kitchen', minutes=300)]
        res = tp.distribute(people, tp.HYBRID)
        by = {r.key: r.share for r in res.rows}
        self.assertLess(by['srv'], 10000, "the tip-out never happened")
        self.assertGreater(by['kit'], 0, "support staff received no tip-out")
        self.assertEqual(res.total, res.pool)

    def test_11_a_server_who_captured_nothing_tips_out_nothing(self):
        people = [P('a', role='server', minutes=300, captured=10000),
                  P('b', role='server', minutes=300, captured=0)]
        res = tp.distribute(people, tp.HYBRID)
        self.assertEqual(res.total, res.pool)

    # -- refusals ----------------------------------------------------------
    def test_12_an_empty_shift_and_an_unknown_rule_are_refused_not_crashed(self):
        self.assertEqual(tp.distribute([], tp.HOURS).err, tp.ERR_NO_ONE)
        self.assertEqual(tp.distribute([P('a')], 'by_vibes').err, tp.ERR_UNKNOWN_RULE)

    def test_13_no_hours_on_shift_refuses_rather_than_dividing_by_zero(self):
        people = [P('a', minutes=0, captured=5000), P('b', minutes=0)]
        res = tp.distribute(people, tp.HOURS)
        self.assertEqual(res.err, tp.ERR_NO_WEIGHT)
        self.assertEqual(res.total, 0)

    def test_14_allocation_is_deterministic(self):
        """Same input, same shares — a run must re-read identically."""
        people = [P('a', minutes=100, captured=1000), P('b', minutes=100),
                  P('c', minutes=100)]
        runs = [tp.distribute(people, tp.HOURS).rows for _ in range(5)]
        for r in runs[1:]:
            self.assertEqual(r, runs[0])
