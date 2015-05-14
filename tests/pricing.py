import unittest
import json
import requests
import sys
import string
import random

import config
import core.content.errors as errors
import core.api.main as main
import core.content.content as content
import core.pricing.pricing as pricing
import core.storage as storage

from core.util.test import *

class TestPricingEngine(unittest.TestCase):


	def testLoadEmptyPrices(self):
		backend = content.Content()
		a = backend.addApplication('Test')
		p = pricing.PricingEngine.getApplicationPricing(a.key)

		self.assertEqual(p.groupAPrices, None)
		self.assertEqual(p.groupBPrices, None)


	def testLoadPrices(self):
		backend = content.Content()
		a = backend.addApplication('Test')
		
		jsonPrices = backend.addPrices(a.key, 'JSON', json.dumps({'sword':1000}), None)

		backend.setABTest(a.key, {'groupAPrices_key': jsonPrices.key})

		p = pricing.PricingEngine.getApplicationPricing(a.key)

		self.assertNotEqual(p.groupAPrices, None)
		self.assertEqual(p.groupBPrices, None)


	def testPricesWithProgress(self):
		backend = content.Content()
		a = backend.addApplication('Test')
		
		jsonPricesA = backend.addPrices(a.key, 'JSON', json.dumps({'sword':1000}), None)
		jsonPricesB = backend.addPrices(a.key, 'JSON', json.dumps({'sword':2000}), None)

		backend.setABTest(a.key, {'groupAPrices_key': jsonPricesA.key})
		backend.setABTest(a.key, {'groupBPrices_key': jsonPricesB.key})

		pricing = backend.getPricingEngine(a.key)
		
		pricesA = pricing.getPrices('a', [0]*32)
		pricesB = pricing.getPrices('b', [0]*32)
		
		self.assertEqual(pricesA[0], jsonPricesA.key)
		self.assertEqual(pricesB[0], jsonPricesB.key)
		self.assertEqual(pricesA[1]['sword'][0], 1000)
		self.assertEqual(pricesB[1]['sword'][0], 2000)
		

	def testPricesWithBadApplicationKey(self):
		backend = content.Content()
		with self.assertRaises(pricing.ApplicationNotFoundException):
			applicationPrices = backend.getPricingEngine('12345')
		
class TestJSONEngine(unittest.TestCase):		
	def testEngine(self):
		p = pricing.JSONDataEngine.validate({'data': json.dumps({'sword':1000})})
		self.assertIsInstance(p, dict)

		p = pricing.JSONDataEngine.validate({'data': json.dumps({'sword':[1000]+[None]*7})})
		self.assertIsInstance(p, dict)

		with self.assertRaises(pricing.DataEngineException):
			p = pricing.JSONDataEngine.validate({'data': json.dumps({'sword':'1000'})})
		
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.JSONDataEngine.validate({'data': json.dumps({'sword':[1,2,3,4,5,6,7,8,9]})})
		
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.JSONDataEngine.validate({'data': json.dumps({'sword':[1,2,3,'4',5,6,7,8,9]})})
	



class TestCSVEngine(unittest.TestCase):

	def testEngine(self):
		data = """
			sword, 1000
			saber, 2000
			knife, 500
		"""	
		p = pricing.CSVDataEngine.validate({'data': data})
		self.assertIsInstance(p, dict)

		data = """
			sword, 1000, 300
			saber, 2000, 400
			knife, 500
		"""	
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.CSVDataEngine.validate({'data': data})
		data = """
			sword,
			saber, 2000, 400
			knife, 500
		"""	
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.CSVDataEngine.validate({'data': data})
		data = """
			sword, "100"
			saber, 2000, 400
			knife, 500
		"""	
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.CSVDataEngine.validate({'data': data})

	def testPath(self):
		backend = content.Content()
		a = backend.addApplication('Test')
		
		data = """
			sword, 1000
			saber, 2000
			knife, 500
		"""	

		fileStorage = storage.getStorage(config.PricingStorage)
		fileStorage.save('test.csv', data)

		csvPrices = backend.addPrices(a.key, 'CSV', None, 'test.csv')

		backend.setABTest(a.key, {'groupAPrices_key': csvPrices.key})
		backend.setABTest(a.key, {'groupBPrices_key': csvPrices.key})
		
		p = pricing.PricingEngine.getApplicationPricing(a.key)

		self.assertNotEqual(p.groupAPrices, None)
		self.assertNotEqual(p.groupBPrices, None)

		prices = p.getPrices('1'*32, [None]*32)
		


class TestMetricCSVEngine(unittest.TestCase):
	def __makeProgress(self, p, v):
		return [None]*(p-1) + [v] + [None]*(32-p)

	def testEngine(self):
	
		data = """
			metricString5, Default, US, BR, DE
			sword, 100, 200, 300, 500
			saber, 200, 300, 400, 600
			knife, 300, 400, 500, 700

		"""
		p = pricing.MetricCSVDataEngine({'data':data})
		self.assertEqual(p.getPrices(self.__makeProgress(5, 'US'))['sword'][0], 200)
		self.assertEqual(p.getPrices(self.__makeProgress(5, 'BR'))['saber'][0], 400)
		self.assertEqual(p.getPrices(self.__makeProgress(5, 'DE'))['knife'][0], 700)
		self.assertEqual(p.getPrices(self.__makeProgress(5, 'JP'))['knife'][0], 300)

		# Check number metric conversion 
		data = """
			metricString8, Default, A, B, C
			sword, 100, 200, 300, 500
		"""
		p = pricing.MetricCSVDataEngine.validate({'data':data})

		# Check number metric conversion 
		data = """
			metricNumber1, Default, 1, 2, 3
			sword, 100, 200, 300, 500
		"""
		p = pricing.MetricCSVDataEngine.validate({'data':data})


		# Check number metric conversion 
		data = """
			metricNumber5, Default, 10, 20, 30
			sword, 100, 200, 300, 500
		"""
		p = pricing.MetricCSVDataEngine.validate({'data':data})
		self.assertEqual(p['metric'], 12)

		# Metric number out of bound
		data = """
			metricNumber40, Default, 10, 20, 30
			sword, 100, 200, 300, 500
		"""
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.MetricCSVDataEngine.validate({'data':data})
		
		# Unrecognized metric
		data = """
			something12, Default, US, BR, DE
			sword, 100, 200, 300, 500
		"""
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.MetricCSVDataEngine.validate({'data':data})

		# Row with missing column
		data = """
			metricNumber5, Default, 10, 20, 30
			sword, 100, 200, 300
		"""
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.MetricCSVDataEngine.validate({'data':data})

		# Row with too many elements
		data = """
			metricNumber5, Default, 10, 20, 30
			sword, 100, 200, 300, 400, 500
		"""
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.MetricCSVDataEngine.validate({'data':data})

		# Row with wrong type of value
		data = """
			metricNumber5, Default, US, BR, DE
			sword, 100, 200, 'abc', 400, 500
		"""
		with self.assertRaises(pricing.DataEngineException):
			p = pricing.MetricCSVDataEngine.validate({'data':data})






suite = unittest.TestSuite()
suite.addTests(discoverTests(TestPricingEngine))
suite.addTests(discoverTests(TestCSVEngine))
suite.addTests(discoverTests(TestJSONEngine))
suite.addTests(discoverTests(TestMetricCSVEngine))

unittest.TextTestRunner(verbosity=2).run(suite)


