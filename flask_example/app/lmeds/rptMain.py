#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from os.path import join

import cgi
import cgitb
cgitb.enable()

import __main__

import codecs

from lmeds import factories
from lmeds import html
from lmeds import audio
from lmeds import sequence
from lmeds import loader
from lmeds import constants

# First page (name page) + consentPage + instructionsPage + ?
#numExtraneousPages = 3

#CONSENT_PAGE = 1
#totalNumPages = loader.readGetNumItems()
#FINAL_PAGE = totalNumPages + numExtraneousPages


class WebSurvey(object):
    
    
    def __init__(self, surveyName, sequenceFN, languageFileFN, 
                 disableRefreshFlag, sourceCGIFN=None):
        
        self.surveyRoot = join(constants.rootDir, "tests", surveyName)
        self.wavDir = join(self.surveyRoot, "audio")
        self.txtDir = join(self.surveyRoot, "txt")
        self.outputDir = join(self.surveyRoot, "output")
        
        self.surveyName = surveyName
        self.sequenceFN = join(self.surveyRoot, sequenceFN)
        self.testSequence = sequence.TestSequence(self, self.sequenceFN)
        self.languageFileFN = join(self.surveyRoot, languageFileFN)
        loader.initTextDict(self.languageFileFN)
        
        self.disableRefreshFlag = disableRefreshFlag
        
        # The sourceCGIFN is the CGI file that was requested from the server
        # (basically the cgi file that started the websurvey)
        self.sourceCGIFN = None
        if sourceCGIFN == None:
            self.sourceCGIFN = os.path.split(__main__.__file__)[1]
#        self.sourceCGIFN = os.path.splitext(self.sourceCGIFN)
    
    
    def run(self):
        import cgitb
        cgitb.enable()    
        
        cgiForm = cgi.FieldStorage()
        
        # The user has not started the test
        if not cgiForm.has_key("pageNumber"):
            cookieTracker = 0 # This value is irrelevant but it must always increase
                                # --if it does not, the program will suspect a refresh-
                                #    or back-button press and end the test immediately
            pageNum = 0 # Used for the progress bar
#             page = [('main', 0, ('login', [], {})),] # The initial state
#             page = newPage.loginPage()
            page = self.testSequence.getPage(0)
            userName = ""
        
        # Extract the information from the form
        else:
            pageNum, cookieTracker, page, userName = self.processForm(cgiForm, self.testSequence)
            
        
        return self.buildPage(pageNum, cookieTracker, page, userName, self.testSequence, self.sourceCGIFN)
    
    
    def runDebug(self, page, pageNum=1, cookieTracker=True, userName="testing"):
        
        testSequence = sequence.TestSequence(self.sequenceFN)
        return self.buildPage(pageNum, cookieTracker, page, userName, testSequence, self.sourceCGIFN)


    def processForm(self, form, testSequence):
        '''
        Get the page number and user info from the previous page; serialize user data
        '''
        
        userName = ""
        
        
        cookieTracker = int(form["cookieTracker"].value)
        cookieTracker += 1
        
        pageNum = int(form["pageNumber"].value)
        lastPage = self.testSequence.getPage(pageNum)
        lastPageNum = pageNum
        
        # This is the default next page, but in the code below we will see
        #    if we need to override that decision        
        pageNum += 1
        sequenceTitle = testSequence.sequenceTitle 
        nextPage = testSequence.getPage(pageNum)
        
        # If a user name text control is on the page, extract the user name from it
        if form.has_key("user_name_init"):
            
            userName = form["user_name_init"].value.decode('utf-8')
            userName = userName.strip()
            
            # Return to the login page without setting the userName if there is 
            # already data associated with that user name
            outputFN = join(self.outputDir, sequenceTitle, userName+".txt")
            outputFN2 = join(self.outputDir, sequenceTitle, userName+".csv")
            nameAlreadyExists = os.path.exists(outputFN) or os.path.exists(outputFN2)
            
            if nameAlreadyExists or userName == "":
                nextPage = factories.loadPage(self, "login_bad_user_name", [userName,], {})
                pageNum -= 1 # We wrongly guessed that we would be progressing in the test
         
        # Otherwise, the user name, should be stored in the form    
        elif form.has_key("user_name"):
            userName = form["user_name"].value.decode('utf-8')  
        
        # Serialize all variables
        self.serializeResults(form, lastPage, lastPageNum, userName, sequenceTitle)
        
        # Go to a special end state if the user does not consent to the study
        if lastPage.sequenceName == 'consent':
            if form['radio'].value == 'dissent':
                nextPage = factories.loadPage(self, "consent_end")
    
        # Go to a special end state if the user cannot play audio files
        if lastPage.sequenceName == 'audio_test':
            if form['radio'].value == 'dissent':
                nextPage = factories.loadPage(self, "audio_test_end", [], {})
    
        return pageNum, cookieTracker, nextPage, userName
    
    
    def getNumOutputs(self, testType, fnFullPath):
        numOutputs = 0 # All non-trial pages do not have any outputs
        if testType in ['prominence', 'boundary', 'oldProminence',
                        'oldBoundary', 'boundary_and_prominence']:
            wordList = loader.loadTxt(fnFullPath)
            numOutputs = 0
            for line in wordList:
                numOutputs += len(line.split(" "))
            
            if testType == 'oldBoundary':
                numOutputs -= 1
                
            if testType == 'boundary_and_prominence':
                numOutputs *= 2
        
        elif testType in ['axb',"same_different"]:
            numOutputs = 2 # A, B
            
        elif testType in ['abn',]:
            numOutputs = 3 # A, B, N
            
        return numOutputs
    
    
    def buildPage(self, pageNum, cookieTracker, page, userName, testSequence, sourceCGIFN):  
        html.printCGIHeader(cookieTracker, self.disableRefreshFlag)
        
    #    print page
#         testType, argList, kargDict = task
        validateText = page.getValidation()
        
    
        # Defaults
        embedTxt = audio.generateEmbed(self.wavDir, [])
#         embedTxt += "goodbye"
#         embedTxt += html.getProcessSubmitHTML(testType)
#         embedTxt += "hello"
        
#         validateText = validation.getValidationForPage(testType)
        
        # Estimate our current progress (this doesn't work well if the user
        #    can jump around)
        totalNumPages = float(len(testSequence.testItemList))
        percentComplete = int(100*(pageNum)/(totalNumPages - 1))
        
        htmlTxt, pageTemplateFN, updateDict = page.getHTML()
        htmlTxt = html.getLoadingNotification() + htmlTxt
        testType = page.sequenceName
#         try:
#             name = argList[0]
#             txtFN = join(self.txtDir, name+".txt")
#             numItems = self.getNumOutputs(testType, txtFN)
#         except IndexError:
#             numItems = 0
        
        numItems = page.getNumOutputs()
        
        # Also HACK
        processSubmitHTML = page.getProcessSubmitFunctions()
        

        
    #    print cookieTracker, pageNum, testType, argList
        
        # HACK
        if testType == 'boundary_and_prominence':
            formHTML = html.formTemplate2
        else:
            formHTML = html.formTemplate
        # -*- coding: utf-8 -*-


        submitWidgetList = []
        if page.submitProcessButtonFlag:
            submitButtonHTML = html.submitButtonHTML % loader.getText('continue button')
            submitWidgetList.append( ('widget', "submitButton"), ) 
        else:
            submitButtonHTML = "" 
        
        submitWidgetList.extend(page.nonstandardSubmitProcessList)

        runOnLoad = ""          
        submitAssociation = html.constructSubmitAssociation(submitWidgetList)
    	runOnLoad += submitAssociation    
	
        if page.getNumAudioButtons() > 0:
        	runOnLoad += audio.loadAudioSnippet
        processSubmitHTML += html.taskDurationCode % runOnLoad
            
        jqueryCode = """<script src="jquery-1.11.0.min.js"></script>\n"""
        processSubmitHTML = jqueryCode + processSubmitHTML
            
        if 'embed' in updateDict.keys():
            updateDict['embed'] = processSubmitHTML + updateDict['embed']
        else:
            embedTxt += processSubmitHTML
            
        progressBarHTML = html.getProgressBar()  % {'percentComplete': percentComplete,
                                                      'percentUnfinished': 100 - percentComplete,}
                
        # FIXME: Optional for now.  Will be required in the future
        try:
            metaDescription = loader.getText("metadata_description")
        except loader.TextNotInDictionaryException:
            metaDescription = ""
                
        audioPlayTrackingHTML = ""
        for i in xrange(page.getNumAudioButtons()):
            audioPlayTrackingHTML += html.audioPlayTrackingTemplate % {"id":i}
                
        htmlDict = { 
                     'html':htmlTxt,
                     'pageNumber':pageNum,
                     'cookieTracker':cookieTracker,
                     'page':page,
                     'user_name':userName,
                     'validate':validateText,
                     'embed':embedTxt,
                     'metadata_description':metaDescription,
                     'websiteRootURL': constants.rootURL,
                     'program_title':constants.softwareName,
                     'source_cgi_fn':sourceCGIFN,
                     'num_items':numItems,
                     'audio_play_tracking_html':audioPlayTrackingHTML,
                     'submit_button_slot': submitButtonHTML,
                                     }
        
        
        pageTemplate = open(pageTemplateFN, "r").read()
        pageTemplate %= {'form':formHTML,
                         'progressBar': progressBarHTML,
                         'pressBackWarning': loader.getText('back button warning')}
        htmlDict.update(updateDict)
    
        htmlOutput = pageTemplate % htmlDict
        
        retval = htmlOutput.encode('utf-8')
        print 'rptMain ' + retval + '\n'
        return retval  #added return used to be print    
    
    def _getLeafSequenceName(self, page):
        '''
        Sequences can contain many subsequences--this fetches the leaf sequence
        '''
        
        if type(page[-1]) == type(()):
            retValue = self._getLeafSequenceName(page[-1])
        else:
            retValue = page[0]
            
        return retValue 
    
    
    def getoutput(self, key, form):
        '''
        
        Output from the cgi form is the name of the indices that were marked positive.
        Here we use the convention that checkboxes are ordered and named as such
        (e.g. "1", "2", "3", etc.).
        
        This code converts this list into the full list of checked and unchecked
        boxes, where the index of the item in the row contains the value of the 
        corresponding checkbox
        e.g. for 'Tom saw Mary' where each word can be selected by the user,
        the sequence [0, 0, 1] would indicate that 'Mary' was selected and 'Tom' 
        and 'saw' were not.
        '''
        numItems = int(form.getvalue('num_items'))
        
        # Contains index of all of the positively marked items (ignores unmarked items)
        outputList = form.getlist(key)
    
        # Assume all items unmarked
        retList = ["0" for i in xrange(numItems)]
        
        # Mark positively marked items
        for i in outputList:
            retList[int(i)] = "1"
        
        return key, ",".join(retList)
    
    
    def serializeResults(self, form, page, pageNum, userName, sequenceTitle):
        
        # The arguments to the task hold the information that distinguish
        #    this trial from other trials
#         currentPage = page[-1]

        taskName, taskArgumentStr = self.testSequence.getPageStr(pageNum)

        numPlays1 = form.getvalue('audioFilePlays0')
        numPlays2 = form.getvalue('audioFilePlays1')
        taskDuration = form.getvalue('task_duration')
        
        key = page.sequenceName
        value = page.getOutput(form)
        
        # Serialize data
#         for key, value in outputList:
        experimentOutputDir = join(self.outputDir, sequenceTitle)
        if not os.path.exists(experimentOutputDir):
            os.mkdir(experimentOutputDir)
            
#         outputDir = join(experimentOutputDir, key)
#         if not os.path.exists(outputDir):
#             os.mkdir(outputDir)
            
        outputFN = join(experimentOutputDir, "%s.csv" % (userName))
        fd = codecs.open(outputFN, "aU", encoding="utf-8")
        fd.write( "%s,%s,%s,%s,%s;,%s\n" % (key,taskArgumentStr,numPlays1, numPlays2, taskDuration, value))    
        fd.close()


    

if __name__ == "__main__":
    survey = WebSurvey("perceptDiscourse", "sequence_test.txt", "english.txt", False)
#    survey.run()
    survey.runDebug([('main', 1, ('boundary_and_prominence', ['s01-1-test2', 'meaning',]))], cookieTracker=False)
   
#     runCGI()
#     
#    print "hello"
    
    
    