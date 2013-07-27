from collections import namedtuple

import mock
import unittest2


class CycleTimeDistributionReportTests(unittest2.TestCase):
    def setUp(self):
        self.HistogramRow = namedtuple('HistogramRow',
            ['days', 'count', 'percent']
        )

    def _get_target_class(self):
        from kardboard.services.reports import CycleTimeDistribution
        return CycleTimeDistribution

    def _create_cards(self, cycle_times, service_classes=None):
        """Helper method to create cards with the
        given cycle times and optional service classes"""
        if service_classes is None:
            service_classes = []
            for ctime in cycle_times:
                service_classes.append('default')
        data = zip(cycle_times, service_classes)

        cards = []
        for ctime, sclass_name in data:
            k = mock.Mock()
            k.cycle_time = ctime
            k.service_class = {'name': sclass_name}
            cards.append(k)
        return cards

    def test_create_cards_helper_returns_cards(self):
        ctimes = [1, 3, 3]
        cards = self._create_cards(ctimes)
        assert len(cards) == 3

    def test_create_cards_helper_returns_times(self):
        ctimes = [1, 3, 3]
        cards = self._create_cards(ctimes)
        actual_ctimes = [c.cycle_time for c in cards]
        actual_ctimes.sort()
        assert ctimes == actual_ctimes

    def test_create_cards_helper_returns_sclasses(self):
        ctimes = [1, 3, 1, 3, 4]
        sclasses = [
            'Expedite',
            'Standard',
            'Standard',
            'Expedite',
            'Intangible',
        ]
        cards = self._create_cards(ctimes, sclasses)
        actual_sclasses = [c.service_class.get('name') for c in cards]
        actual_sclasses.sort()
        sclasses.sort()
        assert sclasses == actual_sclasses

    def test_data_table_returns_counts(self):
        cycle_times = [0, 1, 5, 3, 2, 5, 3]
        cards = self._create_cards(cycle_times)

        CDR = self._get_target_class()
        cdr = CDR(cards=cards)

        expected = [
            self.HistogramRow(
                days=0,
                count=1,
                percent=1 / float(7)
            ),
            self.HistogramRow(
                days=1,
                count=1,
                percent=2 / float(7)
            ),
            self.HistogramRow(
                days=2,
                count=1,
                percent=3 / float(7)
            ),
            self.HistogramRow(
                days=3,
                count=2,
                percent=5 / float(7)
            ),
            self.HistogramRow(
                days=5,
                count=2,
                percent=7 / float(7)
            ),
        ]

        assert expected == cdr.histogram()
