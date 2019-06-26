import os
import sys
import json
from bs4 import BeautifulSoup
from subprocess import Popen, PIPE, STDOUT
import time
from elasticsearch import Elasticsearch
import dateparser
import re
from pprint import pprint

mmExec = sys.argv[1] #first argument must be path to metamath executable
mmFile = sys.argv[2] #second argument must be path to *.mm file
esURL = sys.argv[3] #third argument must be elasticsearch url
esIndex = sys.argv[4] #fourth argument must be name of elasticsearch index
command = sys.argv[5] #fifth argument must be command (initialise, add <optional file list, if none adds those which are missing>, delete <file list>, show <optional file list, if none shows all>)
labels = sys.argv[6:] #sixth argument onwards is optional file list for add, delete, show

if len(sys.argv) < 5:
    quit()
if command not in "initialise delete add show".split():
    quit()
if command == "delete" and len(labels) == 0:
    quit()
if command == "initialise" and len(labels) > 0:
    quit()


#communicate with metamath
mmTermString = """MM>     ^
?Expected DBG, HELP, READ, WRITE, PROVE, SHOW, SEARCH, SAVE, SUBMIT, OPEN,
CLOSE, SET, FILE, BEEP, EXIT, QUIT, ERASE, VERIFY, MARKUP, MORE, TOOLS, or
MIDI.
"""
mmProc = Popen([mmExec], stdin = PIPE, stdout = PIPE, stderr = STDOUT)
def mm(string):
    mmProc.stdin.write((string+"\n.\n").encode())
    mmProc.stdin.flush()
    output = ""
    while True:
        output += mmProc.stdout.readline().decode()
        if output[len(output)-len(mmTermString):] == mmTermString:
            return output[4:len(output)-len(mmTermString)]

#a common trick to extract certain types of html
def getHTMLParagraph(soup, string):
            htmlBlock = soup.find("b", string=string)
            if htmlBlock is not None:
                bold = htmlBlock
                htmlBlock = htmlBlock.parent.parent.parent
                bold.decompose()
                return htmlBlock.prettify()

#remove unnecessary spaces
def reduceSpacing(string):
    if len(string) == 0:
        return string
    length = 0
    while length != len(string):
        length = len(string)
        string = string.replace("  ", " ")
    string = string.replace("\n ", "\n")
    if string[0] == " " or string[0] == "\n":
        string = string[1:]
    if len(string) == 0:
        return string
    if string[len(string)-1] == " " or string[len(string)-1] == "\n":
        string = string[:len(string)-1]
    return string

#set up metamath
mm("set scroll continuous")
mm("read \'"+mmFile+"\'")

#set up elasticsearch
es = Elasticsearch([esURL], timeout=30, max_retries=10, retry_on_timeout=True)
if command == "initialise":
    es.indices.delete(index=esIndex,ignore=[404])
    es.indices.create(index=esIndex, body={
        "settings": {
            "analysis": {
                "analyzer": {
                    "metamath": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": [
                                "shingle",
                        ],
                    },
                    "html_text": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "char_filter": [
                            "html_strip",
                        ],
                        "filter": [
                            "asciifolding",
                            "lowercase",
                            "kstem",
                            "shingle",
                        ]
                    },
                    "html_metamath": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "char_filter": [
                            "html_strip",
                        ],
                        "filter": [
                            "shingle",
                        ]
                    }
                },
            }
        },
        "mappings": {
            "properties": {
                "name": {
                    "type": "text",
                    "analyzer": "keyword",
                },
                "usage":{
                    "type": "text",
                    "analyzer": "standard",
                },
                "source":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "proof":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "statementNumber":{
                    "type" : "integer",
                },
                "comment":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "contributor":{
                    "type": "text",
                    "analyzer": "keyword",
                },
                "date":{
                    "type" : "date",
                },
                "statement":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "hypotheses":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "optionalHypotheses":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "requiredVariables":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "allowedVariables":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "containedVariables":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "disjointPairs":{
                    "type": "text",
                    "analyzer": "metamath",
                },
                "html":{
                    "properties": {
                        "comment":{
                            "type": "text",
                            "analyzer": "html_text",
                            "fields": {
                                "metamath": {
                                    "type": "text",
                                    "analyzer": "html_metamath",
                                }
                            }
                        },
                        "syntaxHints":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                        "axioms":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                        "dependencies":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                        "usage":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                        "hypotheses":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                        "statement":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                        "proof":{
                            "type": "text",
                            "analyzer": "html_metamath",
                        },
                    }
                }
            }
        }
    })

#get list of labels
if len(labels) == 0:
    labels = mm("show label *")
    labels = labels.split("The assertions that match are shown with statement number, label, and type.\n")[1]
    labels = labels.replace("\n", " ")
    labels = labels.split("$")
    labels[0] = "p "+labels[0]
    labels = [label.split()[2] for label in labels[:len(labels)-1]]

#iterate through labels
for labelIndex, label in enumerate(labels):
    if command == "add" and es.exists(index=esIndex,id=label):
        print("skipped",label,"("+str(labelIndex+1)+"/"+str(len(labels))+")")
        continue
    elif command == "delete":
        es.delete(index=esIndex,id=label)
        print("deleted",label,"("+str(labelIndex+1)+"/"+str(len(labels))+")")
    else:
        theorem = {"name":label}

        #get html
        mm("show statement "+label+" / alt_html")

        htmlFile = open(label+".html")
        htmlString = htmlFile.read()
        htmlFile.close()
        os.remove(label+".html")

        htmlString = htmlString.replace("\n"," ")
        soup = BeautifulSoup(htmlString, "html.parser")
        theorem["html"] = {}

        #add html comment, syntax hints, axioms, dependencies, usage
        theorem["html"]["comment"] = getHTMLParagraph(soup, "Description: ")
        theorem["html"]["syntaxHints"] = getHTMLParagraph(soup, "Syntax hints:")
        theorem["html"]["axioms"] = getHTMLParagraph(soup, "This theorem was proved from axioms:")
        theorem["html"]["dependencies"] = getHTMLParagraph(soup, "This theorem depends on definitions:")
        theorem["html"]["usage"] = getHTMLParagraph(soup, "This theorem is referenced by:")
        if theorem["html"]["usage"] is not None and "(None)" in theorem["html"]["usage"]:
            del theorem["html"]["usage"]

        #add html hypotheses
        htmlHypotheses = soup.find("table", attrs={"summary":"Hypotheses"})
        if htmlHypotheses is not None:
            htmlHypotheses.attrs = {}
            theorem["html"]["hypotheses"] = htmlHypotheses.prettify()
        else:
            htmlHypotheses = soup.find("table", attrs={"summary":"Hypothesis"})
            if htmlHypotheses is not None:
                htmlHypotheses.attrs = {}
                theorem["html"]["hypotheses"] = htmlHypotheses.prettify()

        #add html statement
        htmlStatement = soup.find("table", attrs={"summary": "Assertion"})
        if htmlStatement is not None:
            htmlStatement.attrs = {}
            theorem["html"]["statement"] = htmlStatement.prettify()

        #add html proof
        htmlProof = soup.find("table", attrs={"summary":"Proof of theorem"})
        if htmlProof is not None:
            htmlProof.attrs = {}
            theorem["html"]["proof"] = htmlProof.prettify()



        #add usage
        usage = mm("show usage "+label).split("statements:\n")
        if len(usage) > 1:
            usage = usage[1]
            usage = usage.replace("\n", " ")
            usage = usage.split()
            theorem["usage"] = usage

        #add source
        theorem["source"] = mm("show source "+label)

        #add proof
        proof = mm("show proof "+label)
        if proof.startswith("?There is no $p statement whose label matches"):
            proof = None
        else:
            theorem["proof"] = proof

        #get show statement / full
        details = mm("show statement "+label+" / full")

        #add statement number
        statementNumber = details[10:].split()[0]
        theorem["statementNumber"] = statementNumber

        #add comment
        theorem["comment"] = details.split(".\n\"")[1].split("\"\n"+statementNumber+" "+label)[0]

        #add contributor and date, and remove them from description
        contribString = "\([\n\r\s]{0,}Contributed[\n\r\s]{1,}by[\n\r\s]{1,}"
        hcom = re.search(contribString+"([^]]+?)\.\)",theorem["html"]["comment"])
        com = re.search(contribString+"([^]]+?)\.\)",theorem["comment"])
        if hcom:
            theorem["html"]["comment"] = re.sub(contribString+"([^]]+?)\.\)","",theorem["html"]["comment"])
            contribSplit = hcom.group(0).split()
            date = contribSplit[len(contribSplit)-1].replace(".)","")
            contributor = " ".join(contribSplit[:len(contribSplit)-1]).replace(",","")
            contributor = re.sub(contribString,"",contributor)
            theorem["contributor"] = contributor
            theorem["date"] = dateparser.parse(date)

        if com:
            theorem["comment"] = re.sub(contribString+"([^]]+?)\.\)","",theorem["comment"])

        #add statement, hypotheses, disjointPairs, optionalHypotheses, requiredVariables, allowedVariables, containedVariables
        sectionHeaders = {
            "Its mandatory hypotheses in RPN order are:":"@@@hypotheses~~~",
            "Its mandatory disjoint variable pairs are:":"@@@disjointPairs~~~",
            "Its optional hypotheses are:":"@@@optionalHypotheses~~~",
            "The statement and its hypotheses require the variables:":"@@@requiredVariables~~~",
            "These additional variables are allowed in its proof:":"@@@allowedVariables~~~",
            "The variables it contains are:":"@@@containedVariables~~~",
        }
        sections = details
        for key,value in sectionHeaders.items():
            sections = sections.replace(key, value)

        #add statement
        theorem["statement"] = sections.split("\"\n"+statementNumber+" "+label)[1].split("@@@")[0]

        #add optionalHypotheses, requiredVariables, allowedVariables, containedVariables, disjointPairs
        sections = sections.split("@@")
        sections = [s[1:] for s in sections if s[0]=="@"]
        for section in sections:
            split = section.split("~~~")
            key = split[0]
            value = split[1]
            theorem[key] = value

        #process optionalHypotheses, requiredVariables, allowedVariables, and containedVariables into lists
        for key in ["optionalHypotheses","requiredVariables","allowedVariables","containedVariables"]:
            if key in theorem:
                theorem[key] = theorem[key].replace("\n", " ")
                theorem[key] = theorem[key].split()

        #process disjointPairs into lists of pairs
        if "disjointPairs" in theorem:
            theorem["disjointPairs"] = theorem["disjointPairs"].replace("\n"," ")
            theorem["disjointPairs"] = reduceSpacing(theorem["disjointPairs"])
            theorem["disjointPairs"] = theorem["disjointPairs"].split(", ")
            for i in range(len(theorem["disjointPairs"])):
                theorem["disjointPairs"][i] = theorem["disjointPairs"][i].replace("<","").replace(">","").split(",")

        #reduce spacing
        for key in theorem:
            if isinstance(theorem[key], str):
                theorem[key] = reduceSpacing(theorem[key])

        #clear empties
        theorem = {k:v for k,v in theorem.items() if v != None}
        theorem["html"] = {k:v for k,v in theorem["html"].items() if v != None}

        #send to elasticsearch
        if command == "add" or command == "initialise":
            es.index(index=esIndex, id=label, body=theorem)
            print("added",label,"("+str(labelIndex+1)+"/"+str(len(labels))+")")
        elif command == "show":
            pprint(theorem)
