from django.shortcuts import render
from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from django.forms.models import model_to_dict


import scrapy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.firefox.options import Options
options = Options()
options.set_headless(headless=True)


from scrapy.crawler import CrawlerProcess, CrawlerRunner

from scrapy.utils.log import configure_logging

from twisted.internet import reactor

import boto3
client = boto3.client('dynamodb')

import json
import re

configure_logging({'LOG_FORMAT': '%(levelname)s: %(message)s'})
runner = CrawlerRunner()

# Object filled with response
toReturn = {}

class GradecheckEndpoint(APIView):
	"""
	API endpoint that allows users to be viewed or edited.
	"""
	def post(self, request):
		data = {
			'username' : request.data['username'],
			'password' : request.data['password']
		}

		
		toReturn['works']  = True

		try:
			spider = runner.crawl(GradecheckSpider, data['username'], data['password'])
			spider.addBoth(lambda _: reactor.stop())
			reactor.run() # the script will block here until the crawling is finished
			pass
		except Exception as e:
			print(e)
			toReturn['works'] = False

		
		
		return JsonResponse(toReturn, safe=False)

class GradeQuery(APIView):
	"""docstring for GradeQuery"""
	def get(self, request):
		data = {
			'username' : request.query_params['username']
		}

		response = client.get_item(
			TableName='Students',
			Key={
				'id': {
					'S': str(data['username'])
				}
			}
		)

		if 'Item' not in response:
			response = False
			pass
		return JsonResponse(response, safe=False)
		

class GradecheckSpider(scrapy.Spider):	
    name     = "gradecheck"
    url      = 'https://muid.unicah.edu/?nv=4'
    username = '0506199402103'
    password = 'RP_unicah00'

    def __init__(self, username, password, is_periodic_check=False, grade_db_data=None):
        self.username = username
        self.password = password
        self.is_periodic_check = is_periodic_check
        self.grade_db_data	   = grade_db_data

    def start_requests(self):
        urls = [
            self.url
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        page = response.url.split("/")[-2]
        token = response.xpath('//input[@name="tk"]/@value').extract_first()

        yield scrapy.FormRequest.from_response(
        response,
        formdata={'tk':token, 'user': self.username, 'password': self.password},
        callback=self.after_login,
        dont_filter = True
        )

    def after_login(self, response):
        session_id = response.xpath('//input[@name="UserPass"]/@value').extract_first()

        if response.xpath("//script[contains(text(), 'Usuario ó contraseña invalidos.')]"):
            print("Wrong password shusho!!")
            print("Wrong password shusho!!")
            print("Wrong password shusho!!")
            print("Wrong password shusho!!")
            toReturn['error'] = "Wrong password"
            return        

        return scrapy.FormRequest(
        url='https://app.unicah.edu/registro/servlet/loginstd',
        formdata={'UserName': self.username, 'UserPass': session_id},
        callback=self.after_muid_login,
        dont_filter = True
        )
    
    def after_muid_login(self, response):
        may_run = True
        if response.xpath("//span[contains(., 'Credenciales de Acceso')]"):
            may_run = False
            print("Another login screen relog!")
            gxData = response.xpath('//input[@name="GXState"]/@value').extract_first()
            try:
            	self.selenium_login_registro(response.url, self.username, self.password)
            	pass
            except Exception as e:            	
            	CloseSpider('Selenium error')
            	toReturn['error'] = "Unkown"
            	raise e            
        if may_run:
            page = response.url.split("/")[-2]                
            grades_link = response.xpath('//img[@id="BTNBOLETANOTAS"]/parent::a/@href').extract_first()
            url = response.urljoin(grades_link)
     
            yield scrapy.Request(url, self.get_grades)        

    def after_muid_login2(self, response):    	
        self.selenium_login_registro(response.url, self.username, self.password)
    
    def parse_gxdata_for_grades(self, json_grades):    	
        student_data = {"Perfil": json_grades['W0003Alumnoperfil'], 
                        "Periodo": json_grades['W0004AV18PeriodoAnio_PARM'],
                        "Trimestre": json_grades['W0004AV17Periodo_PARM'],
                        "Asignaturas": json_grades['W0004nRC_Gridasignaturas_0001'],
                        "Table_Data": json_grades['W0004GridasignaturasContainerData_0001']
                        }

        classes = [ json.loads( student_data['Table_Data'] )[key]['Props'] for key in json.loads( student_data['Table_Data'] ) if (re.match('^\d$', key)) ]

        regex_asignatura = re.compile('^W0004CTLCAMPUSASIGNATURA_\d+$')

        grade_data = []
        
        for topic in classes:
            topic_data = {'title':'', 'grades': [] }
            # print(topic)
            topic_data['title'] = topic[5][1]      
            topic_data['grades'].append( int(topic[9][1]) if len(topic[9])  > 1 else 0 )
            topic_data['grades'].append( int(topic[11][1]) if len(topic[11])  > 1 else 0 )
            topic_data['grades'].append( int(topic[13][1]) if len(topic[13])  > 1 else 0 )
            
            grade_data.append(topic_data)

        if self.is_periodic_check:        	
            if json.dumps(grade_data, ensure_ascii=False).replace('"',"'") == self.grade_db_data:
                print("tis all good")
                print("tis all good")
                print("tis all good")
            else:
                print("mensajito sha.")
                print("mensajito sha.")
                print("mensajito sha.")
                print("mensajito sha.")
            pass
        print(json.dumps(grade_data, ensure_ascii=False).replace('"',"'") )
        print("compare y compruebe con el gallo mas gallo")
        print(self.grade_db_data)
        print("heres where i print all the shizzle")
        return grade_data

    def get_grades(self, response):
        if response.xpath("//span[contains(text(), 'Evaluaciones de Docente Pendientes')]"):
            evaluation_links = response.xpath('//table//tbody//tr//a/@href').extract()
            print("Hay que evaluar docentes shusho!!")
            print("Hay que evaluar docentes shusho!!")
            print("Hay que evaluar docentes shusho!!")
            print("Hay que evaluar docentes shusho!!")
            self.evaluate_teachers( evaluation_links )
            scrapy.Request(url=self.url, callback=self.parse)

        json_grades = json.loads( response.xpath('//input[@name="GXState"]/@value').extract_first() )
        grade_data = self.parse_gxdata_for_grades(self, json_grades)
        self.send_grades_to_db(grade_data)

        page = response.url.split("/")[-2]
        filename = 'grades-%s.html' % page
        with open(filename, 'wb') as f:
            f.write(json.dumps(grade_data).encode())
        self.log('Saved file %s' % filename)
        
        # Returns the grade data string to compare it for grade check polls
        return json.dumps(grade_data)
    def selenium_login_registro(self, url, username, password ):        
        self.driver = webdriver.Firefox(firefox_options=options)
        self.driver.get( url )
        # radios = self.driver.find_elements_by_xpath("//form//input[@value='5']")

        user_input    = self.driver.find_element_by_xpath("//form//input[@id='vUSRNOM']")
        pw_input      = self.driver.find_element_by_xpath("//form//input[@id='vUSRPWD']")
        submit_input  = self.driver.find_element_by_xpath("//form//input[@value='Confirmar']")

        user_input.send_keys(username)
        pw_input.send_keys(password)
        submit_input.click()
        after_login_link = WebDriverWait(self.driver, 15).until(expected_conditions.presence_of_element_located((By.XPATH, '//img[@id="BTNBOLETANOTAS"]')))

        notas_link = self.driver.find_element_by_xpath('//img[@id="BTNBOLETANOTAS"]/parent::a')
        notas_link.click()
        after_registro_link = WebDriverWait(self.driver, 15).until(expected_conditions.presence_of_element_located((By.XPATH, '//div[@id="W0004GridcarrerasContainerDiv"]')))        
        json_grades = json.loads(self.driver.find_element_by_xpath('//input[@name="GXState"]').get_attribute('value'))

        grade_data = self.parse_gxdata_for_grades(json_grades)
        self.send_grades_to_db(grade_data)

        self.driver.quit()
        print("Finished grade scraping")

    def selenium_login(self, url, username, password ):        
        self.driver = webdriver.Firefox(firefox_options=options)

        self.driver.get( url )
        radios = self.driver.find_elements_by_xpath("//form//input[@value='5']")

        user_input    = self.driver.find_element_by_xpath("//form//input[@id='user']")
        pw_input      = self.driver.find_element_by_xpath("//form//input[@id='password']")
        submit_input  = self.driver.find_element_by_xpath("//form//input[@type='submit']")

        user_input.send_keys(username)
        pw_input.send_keys(password)
        submit_input.click()
        after_login_link = WebDriverWait(self.driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, "//form[@id='registro_temp']/parent::div")))

        registro_button = self.driver.find_element_by_xpath("//form[@id='registro_temp']/parent::div")
        registro_button.click()
        after_registro_link = WebDriverWait(self.driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, '//img[@id="BTNBOLETANOTAS"]/parent::a')))

        notas_link = self.driver.find_element_by_xpath('//img[@id="BTNBOLETANOTAS"]/parent::a')
        notas_link.click()
        after_registro_link = WebDriverWait(self.driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, '//img[@id="W0002vEVALUAR_0001"]/parent::a')))

        evaluation_links = self.driver.find_elements_by_xpath('//table//tbody//tr//a')

        for link in evaluation_links:
            after_registro_link = WebDriverWait(self.driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, '//img[@id="W0002vEVALUAR_0001"]/parent::a')))
            evaluation_form_button_link = self.driver.find_element_by_xpath('//img[@id="W0002vEVALUAR_0001"]/parent::a')
            evaluation_form_button_link.click()

            evaluation_buttons = WebDriverWait(self.driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, "//input[@name='W0002CTLPUNTAJE_0001']")))
            radios = self.driver.find_elements_by_xpath("//form//input[@value='5']")
            
            for radio in radios:
                radio.click()
            
            confirmButton = self.driver.find_element_by_xpath("//input[@value='Confirmar']")
            confirmButton.click()

        # End the Session
        self.driver.quit()
        print("finished evaluations")

    def evaluate_teachers(self, links ):
        self.selenium_login(self.url, self.username, self.password)        

    def set_evaluation(self, response):
        self.driver.get(response.url) 
        radios = self.driver.find_elements_by_xpath("//form//input[@value='5']")
            
        for radio in radios:
            radio.click();
        
        confirmButton = self.driver.find_element_by_xpath("//input[@value='Confirmar")
        confirmButton.click()


    def send_grades_to_db(self, grade_data ):        
        student_id       = self.username
        student_password = self.password
        response = client.update_item(TableName='Students', 
        								Key={'id':{'S':str(student_id)}}, 
        								AttributeUpdates={	
        									"grades":{"Action":"PUT","Value":{"S":str(grade_data)}},
        									"pw":{"Action":"PUT","Value":{"S":str(student_password)}}
        								})
        return grade_data



