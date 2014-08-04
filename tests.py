#!/usr/bin/env python3

import collections
import decimal
import jqsh.values
import unittest

class JQSHTests(unittest.TestCase):
    def test_value_abcs(self):
        with self.assertRaises(TypeError):
            jqsh.values.Value()
        jqsh.values.JQSHException('testException')
        jqsh.values.Null()
        jqsh.values.Null(None)
        jqsh.values.Boolean()
        jqsh.values.Boolean(False)
        jqsh.values.Boolean(True)
        jqsh.values.Number()
        jqsh.values.Number(-3)
        jqsh.values.Number(decimal.Decimal('813' * 813 + '.5'))
        jqsh.values.String()
        jqsh.values.String('')
        jqsh.values.String('this is an example of a jqsh string')
        jqsh.values.Array()
        jqsh.values.Array('foo', jqsh.values.String('bar'))
        obj = jqsh.values.Object()
        obj.keys()
        obj.values()
        obj.items()
    
    def test_value_equality(self):
        self.assertEqual(jqsh.values.JQSHException('testException'), jqsh.values.JQSHException('testException', extra_stuff='irrelevant metadata'))
        self.assertEqual(jqsh.values.Null(), jqsh.values.Null(None))
        self.assertEqual(jqsh.values.Null(), None)
        self.assertEqual(jqsh.values.Boolean(), jqsh.values.Boolean(False))
        self.assertEqual(jqsh.values.Boolean(), False)
        self.assertEqual(jqsh.values.Number(), jqsh.values.Number(0))
        self.assertEqual(jqsh.values.Number(), 0)
        self.assertEqual(jqsh.values.Number(), 0.0)
        self.assertEqual(jqsh.values.String(), jqsh.values.String(''))
        self.assertEqual(jqsh.values.String('42'), jqsh.values.String(42))
        self.assertEqual(jqsh.values.Array(), jqsh.values.Array([]))
        self.assertEqual(jqsh.values.Object([('foo', True), ('bar', False)]), collections.OrderedDict([('bar', False), ('foo', jqsh.values.Boolean(True))]))
    
    def test_value_sorting(self):
        values = [
            jqsh.values.JQSHException('testException'),
            jqsh.values.Null(),
            jqsh.values.Boolean(),
            jqsh.values.Boolean(True),
            jqsh.values.Number(-3),
            jqsh.values.Number(),
            jqsh.values.Number(decimal.Decimal('813' * 813 + '.5')),
            jqsh.values.String(),
            jqsh.values.String('this is an example of a jqsh string'),
            jqsh.values.String('x'),
            jqsh.values.Array(),
            jqsh.values.Array('foo', jqsh.values.String('bar')),
            jqsh.values.Object(),
            jqsh.values.Object([('foo', True), ('bar', False)])
        ]
        for i in range(len(values) - 1):
            for j in range(i + 1, len(values)):
                self.assertLess(values[i], values[j])

if __name__ == '__main__':
    unittest.main()
