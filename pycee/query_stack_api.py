''' This module contains the logic of accessing stackoverflow,
 retrieving the adequate questions for the compiler error 
 and then choosing the best answer for the error'''
 
import re
import requests
from keyword import kwlist
from bs4 import BeautifulSoup
from difflib import get_close_matches
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.parsers.plaintext import PlaintextParser

from utils import SINGLE_SPACE_CHAR, COMMA_CHAR
from utils import DEFAULT_HTML_PARSER, BASE_URL, BUILTINS


def get_questions(query):
    ''' docstring later '''

    # TODO: add code to check if page contains captcha,
    # in this case Stackoverflow is suspecting on us 
    # and no questions will be retrieve from the page
    
    # get soup the results page
    page = requests.get(query)
    soup = BeautifulSoup(page.content, DEFAULT_HTML_PARSER)

    # find anchors on page (these may contain links)
    links=soup.findAll("a")
    answers=[]
    for i in range(len(links)-1):
        # locate all links
        if (links[i].has_attr('href')):
            temp=links[i]['href']
            # filter out links that do not correspond to answers to question
            if ("/questions/" in temp) and ("https://" not in temp) and ("tagged" not in temp):
                answers.append(temp)
    
    if not answers:
        print('Stack overflow thought we were a bot (in fact are we?)')
        print('To temporarily fix this please open the link below on the browser and do the following:')
        print('1 - Solve the captcha\n2-Close the browser tab\n3- Execute pycee2 again')
        print(query)
        print('Anyway, remember to solve this issue, please ;)')

    return answers


def get_links(answers):
    
    answer_url = [BASE_URL + link for link in answers]
    
    if (len(answer_url) <= 1):
        print("No Results!")
        exit()

    return answer_url

def get_post_ids(urls):
    ''' docstring later '''

    ids=[]
    # start of line number
    beg='https://stackoverflow.com/questions/'

    for url in urls:
        # extract error line
        error_start_line=url.find(beg) + len(beg)
        if (error_start_line != -1):
            url=url[error_start_line:]
            error_end_line=url.find('/')
            if (error_end_line != -1):
                url=url[:error_end_line]
                ids.append(int(url))
            else:
                ids.append(-1)
        else:
            ids.append(-1)
    return ids


def get_votes(link):
    ''' docstring later'''

    # get the results page
    page=requests.get(link)
    soup=BeautifulSoup(page.content, "html5lib")
    # find a attributes on page (these may contain links)
    temp=soup.findAll("div", {"class": "vote"})
    votes=[]
    for div in temp:
        votes.append(int(div.find("span", {"class": "vote-count-post "}).text))
    return votes


def get_answers(link):
    ''' docstring later'''

    page=requests.get(link)
    soup=BeautifulSoup(page.content, "html5lib")
    # collect all answers on page
    answerSections=soup.findAll("div", {"class": "answercell"})
    # answerText will hold all lines of answers individually
    answerText=[]
    # extract lines of answers
    for sec in answerSections:
        foo_descendants=sec.descendants
        for ans in foo_descendants:
            if ans.name == 'div' and ans.get('class', '') == ['post-text']:
                for aLine in ans.text.split("\n"):
                    if aLine.strip() != '':
                        answerText.append(aLine)
                        answerText.append('.')

    return answerText

def get_summary(sentences):
    ''' convert sentences to single string -> not good for code '''

    parser=PlaintextParser.from_string(sentences, Tokenizer("english"))
    # get length of answer(s)
    #numSentences=len(parser.document.sentences)
    length=4  # halve length and round up
    # summarise text
    summariser=LuhnSummarizer()

    return summariser(parser.document, length)


def pretty_printer(summary):
    ''' not in use at the moment '''

    newSummary=summary
    while '\n\n' in newSummary:
        newSummary=newSummary.replace('\n\n', '\n')
    return newSummary


def blank(num):
    ''' not in use at the moment '''
    for _ in range(num):
        print('\n')


############# Answer related code

def identify_code(text):
    ''' retrieve code from the answer body '''

    startTag="<code>"
    endTag="</code>"
    pos=[]  # list to hold code positions

    if startTag in text:
        for i, c in enumerate(text):
            if c == '<':
                if startTag == text[i:i+len(startTag)]:
                    pos.append([])
                    pos[len(pos)-1].append(i+len(startTag))
                    if (text[i-5:i] == "<pre>"):
                        pos[len(pos)-1].append(1)
                    else:
                        pos[len(pos)-1].append(0)
                if endTag == text[i:i+len(endTag)]:
                    pos[len(pos)-1].append(i)

        for i in range(0, len(pos)):
            tmp=pos[i][2]
            pos[i][2]=pos[i][1]
            pos[i][1]=tmp
    return pos


def remove_tags(text):
    ''' docstring later on '''

    text=text.replace("<pre>","*pre*")
    text=text.replace("</pre>","*pre*")
    cleaner=re.compile('<.*?>')
    cleanText=re.sub(cleaner, '', text)
    return cleanText


def replace_code(text, pos, message, offending_line):
    ''' docstring later on '''

    newText=text
    noTags=remove_tags(text)
    noTagsLines=noTags.split('\n')
    error_lines=message.split('\n')
    error_type=None
    for line in error_lines:
        if "Error: " in line:
            error_type=line.split(SINGLE_SPACE_CHAR, 1)[0]

    error_header=error_lines[1]
    QAOffendingLine=None  # Syntax Error only
    QAErrorLine=None
    
    # check for compiler text in question/answer
    regex=r'(File|Traceback)(.+)\n(.+)((\n)|(\n( |\t)+\^))\n(Arithmetic|FloatingPoint|Overflow|ZeroDivision|Assertion|Attribute|Buffer|EOF|Import|ModuleNotFound|Lookup|Index|Key|Memory|Name|UnboundLocal|OS|BlockingIO|ChildProcess|Connection|BrokenPipe|ConnectionAborted|ConnectionRefused|ConnectionReset|FileExists|FileNotFound|Interrupted|IsADirectory|NotADirectory|Permission|ProcessLookup|Timeout|Reference|Runtime|NotImplemented|Recursion|Syntax|Indentation|Tab|System|Type|Value|Unicode|UnicodeDecode|UnicodeEncode|UnicodeTranslate)(Error:)(.+)'
    match=re.search(regex, noTags)
    if (match):
        QAErrorLine=match.group(0).split('\n')[1]
        # ALSO CHECK QUESTION?

    # if SyntaxError we may need to handle differently
    if error_type == 'SyntaxError:' and QAErrorLine:
        if error_header != offending_line:
            for i in range(len(pos)):
                previous=None
                if bool(pos[i][2]) and (match.group(0) not in text[pos[i][0]:pos[i][1]]):
                    for line in text[pos[i][0]:pos[i][1]].split('\n'):
                        if line == QAErrorLine:
                            QAOffendingLine=previous
                        previous=line

            # check previous line
            # if previous line of code, swap and exit
            if (QAOffendingLine):
                QAOffendingLine=QAOffendingLine.strip()
            if (error_header):
                error_header=error_header.strip()
            if (QAErrorLine):
                QAErrorLine=QAErrorLine.strip()

            # print(QAOffendingLine)
            # print(error_header)
            # print(QAErrorLine)
            # print(offending_line)

            for i in reversed(pos):
                x=pos.index(i)
                if (QAOffendingLine in text[pos[x][0]:pos[x][1]]):
                    newText=newText[:pos[x][0]] + \
                        error_header + newText[pos[x][1]:]
                elif (QAErrorLine in text[pos[x][0]:pos[x][1]]):
                    newText=newText[:pos[x][0]] + \
                        offending_line + newText[pos[x][1]:]
            return newText
    if (QAErrorLine == None):
        tmpQAErrorLine=get_close_matches(
            offending_line, noTagsLines, 1, 0.4)
        if (tmpQAErrorLine == []):
            return text
        else:
            QAErrorLine=tmpQAErrorLine[0]
    if ((QAErrorLine == None) or (QAErrorLine == '')):
        return text
    # print(QAErrorLine)
    # if exists, check for similar lines
    possibleLines=[]
    if (QAErrorLine == None):
        possibleLines=get_close_matches(
            QAErrorLine, noTagsLines, 3, 0.4)
        # SequenceMatcher(None,line,line2).ratio()
        # print(possibleLines)
    # if exists, substitute variables
    if len(possibleLines) > 0 or QAErrorLine:
        # tokenise similar to before, may have to group
        userVariables=[]
        userBuiltin=[]
        tokens=re.split(
            r'[!@#$%^&*_\-+=\(\)\[\]\{\}\\|~`/?.<>:; ]', error_header)
        for x in reversed(tokens):
            if ((x not in kwlist) and (x not in BUILTINS)):
                userVariables.append(x)
            else:
                userBuiltin.append(x)
        userVariables=list(reversed(userVariables))
        userBuiltin=list(reversed(userBuiltin))
        # split
        QALine=None
        if (QAErrorLine):
            QALine=QAErrorLine
        else:
            QALine=possibleLines[0]
        if (',' in QALine):
            while ((', ' in QALine) or (' ,' in QALine)):
                QALine=QALine.replace(", ", COMMA_CHAR)
                QALine=QALine.replace(" ,", COMMA_CHAR)
        QAVariables=[]
        tokens=re.split(r'[!@#$%^&*_\-+=\(\)\[\]\{\}\\|~`/?.<>:; ]', QALine)
        for x in reversed(tokens):
            if ((x not in kwlist) and (x not in BUILTINS)):
                QAVariables.append(x)
        QAVariables=list(reversed(QAVariables))

        for word in reversed(QAVariables):
            if (word == ''):
                QAVariables.remove(word)

        for word in reversed(userVariables):
            if not word:
                userVariables.remove(word)

        # print(QAVariables)
        # print(userVariables)

        newQALine=QALine
        if len(userVariables) == len(QAVariables):
            for word, i in enumerate(QAVariables):
                newQALine.replace(word, userVariables[i])

    return newText


def remove_code(text, pos, maxLength, removeBlocks):
    ''' currently unused. was this a previous version of  querystackoverflow.identify_code?'''

    newText=text
    for i in range(len(pos)):
        to_remove=text[pos[len(pos)-1-i][0]:pos[len(pos)-1-i][1]]
        if removeBlocks and bool(pos[len(pos)-1-i][2]):
            newText=newText.replace(to_remove, '')
        elif len(to_remove) > maxLength:
            newText=newText.replace(to_remove, '')
    return newText