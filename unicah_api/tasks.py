from __future__ import absolute_import, unicode_literals
from celery import Celery
from celery.decorators import task
from scrapy.crawler import CrawlerProcess, CrawlerRunner
import boto3
client = boto3.client('dynamodb')

from boto3.dynamodb.conditions import Key, Attr
from .views import GradecheckSpider
from twisted.internet import reactor

runner = CrawlerRunner()
toReturn = {}

@task(name="poll_grade_changes")
def pollGradeChange(*args, **kwargs):
	response = client.scan(
			TableName='Students',
			Select='SPECIFIC_ATTRIBUTES',
			AttributesToGet=[
				'id','pw','grades','active'
			]
		)
	
	data = {}

	spider = None

	for item in response['Items']:
		print("iterando items de scan "+ item['id']['S'])
		data['username'] = item['id']['S']
		data['password'] = item['pw']['S']
		grade_db_data	 = item['grades']['S']		
		spider = runner.crawl(GradecheckSpider, data['username'], data['password'], True, grade_db_data)

	spider.addBoth(lambda _: reactor.stop())	
	reactor.run()
	return "done"