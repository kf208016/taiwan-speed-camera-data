import unittest
from scripts.import_mobile import parse_mobile, apply_reference_coordinates
from scripts.resolve_mobile import resolve


class MobileTests(unittest.TestCase):
    def sample(self, coord=','):
        header = '編號,行政區,取締地點,取締行向,速限Speed,經度,緯度\n'
        return (header + ''.join(f'{i},西區,測試地點{i},雙向,50,{coord}\n' for i in range(10))).encode('utf-8')

    def test_missing_coordinates_are_not_invented(self):
        records = parse_mobile(self.sample())
        self.assertEqual(len(records), 10)
        self.assertIsNone(records[0]['lat'])

    def test_rejects_missing_columns(self):
        with self.assertRaises(ValueError):
            parse_mobile('編號,地點\n1,某處'.encode('utf8'))

    def test_rejects_duplicate_ids(self):
        with self.assertRaises(ValueError):
            parse_mobile(self.sample() + '1,西區,另一處,雙向,50,,\n'.encode('utf8'))

    def test_invalid_speed_is_not_presented_as_speed(self):
        records = parse_mobile(self.sample().replace(b',50,', b',5060,'))
        self.assertEqual(records[0]['limit'], '請查公告')

    def test_intersection_requires_both_consistent_lookups(self):
        records = [{'place':'西區 公益路與精誠路口'}]
        def cross(town, road):
            name = '精誠路' if road == '公益路' else '公益路'
            return [{'name':name,'lat':24.15,'lon':120.65}]
        located, errors = resolve(records, cross)
        self.assertIn(records[0]['place'], located)
        self.assertEqual(errors, [])
        def conflicting(town, road):
            return [{'name': '精誠路' if road == '公益路' else '公益路', 'lat':24.15 if road == '公益路' else 24.16, 'lon':120.65}]
        self.assertEqual(resolve(records, conflicting)[0], {})

    def test_reference_does_not_transfer_to_changed_place(self):
        records = [{'place':'西區 公益路與精誠路口', 'lat':None, 'lon':None}]
        ref = {'locations':{'西區 公益路與精誠路口':{'lat':24.15,'lon':120.65,'precision':'intersection'}}}
        self.assertEqual(apply_reference_coordinates(records,ref)[0]['coordinateType'],'intersection')
        changed = [{'place':'西區 公益路附近','lat':None,'lon':None}]
        self.assertIsNone(apply_reference_coordinates(changed,ref)[0]['lat'])


if __name__ == '__main__':
    unittest.main()
