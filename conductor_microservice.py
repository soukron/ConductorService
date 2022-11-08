import requests
from time import time
from uuid import uuid4
import numpy as np
import re
import os
import openai
from time import time,sleep


embedding_service_host=os.getenv('EMBEDDING_SERVICE_HOST', '127.0.0.1')
embedding_service_port=os.getenv('EMBEDDING_SERVICE_PORT', '999')
nexus_service_host=os.getenv('NEXUS_SERVICE_HOST', '127.0.0.1')
nexus_service_port=os.getenv('NEXUS_SERVICE_PORT', '8888')


def wait_for_service(service_name, service_port):
    while True:
        try:
            return requests.get('http://' + service_name + ':' + service_port)
        except requests.exceptions.ConnectionError:
            print('Waiting for ' + service_name + ' to be reachable...')
            sleep(10)


def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()


def save_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)


openai.api_key = open_file('openaiapikey.txt').rstrip()
service_name = 'conductor_service'
content_prefix = 'Conductor: '
tempo = 30


def gpt3_completion(prompt, engine='text-davinci-002', temp=0.7, top_p=1.0, tokens=1000, freq_pen=0.0, pres_pen=0.0, stop=['asdfasdf', 'asdasdf']):
    max_retry = 5
    retry = 0
    prompt = prompt.encode(encoding='ASCII',errors='ignore').decode()
    while True:
        try:
            response = openai.Completion.create(
                engine=engine,
                prompt=prompt,
                temperature=temp,
                max_tokens=tokens,
                top_p=top_p,
                frequency_penalty=freq_pen,
                presence_penalty=pres_pen,
                stop=stop)
            text = response['choices'][0]['text'].strip()
            #text = re.sub('\s+', ' ', text)
            filename = '%s_gpt3.txt' % time()
            save_file('gpt3_logs/%s' % filename, prompt + '\n\n==========\n\n' + text)
            return text
        except Exception as oops:
            retry += 1
            if retry >= max_retry:
                return "GPT3 error: %s" % oops
            print('Error communicating with OpenAI:', oops)
            sleep(1)


def get_embedding(payload):  # payload is a list of strings
    # payload example: ['bacon bacon bacon', 'ham ham ham']
    # response example:  [{'string': 'bacon bacon bacon', 'vector': '[1, 1 ... ]'}, {'string': 'ham ham ham', 'vector': '[1, 1 ... ]'}]
    # embedding is already rendered as a JSON-friendly string
    url = 'http://%s:%s' % (embedding_service_host, embedding_service_port)  # currently the USEv5 service, about 0.02 seconds per transaction!
    response = requests.request(method='POST', url=url, json=payload)
    return response.json()


def nexus_send(payload):  # REQUIRED: content
    url = 'http://%s:%s/add' % (nexus_service_host, nexus_service_port)
    payload['time'] = time()
    payload['uuid'] = str(uuid4())
    payload['content'] = content_prefix + payload['content']
    embeddings = get_embedding([payload['content']])
    payload['vector'] = embeddings[0]['vector']
    payload['service'] = service_name
    response = requests.request(method='POST', url=url, json=payload)
    print(response.text)


def nexus_search(payload):
    url = 'http://%s:%s/search' % (nexus_service_host, nexus_service_port)
    response = requests.request(method='POST', url=url, json=payload)
    return response.json()


def nexus_bound(payload):
    url = 'http://%s:%s/bound' % (nexus_service_host, nexus_service_port)
    response = requests.request(method='POST', url=url, json=payload)
    #print(response)
    return response.json()


def nexus_save():
    url = 'http://%s:%s/save' % (nexus_service_host, nexus_service_port)
    response = requests.request(method='POST', url=url)
    print(response.text)


def save_and_send(content, prefix, tag):
    filename = '%s_%s.txt' % (time(), tag)
    content = prefix + content
    save_file('logs/' + filename, content)
    nexus_send({'content': content})


if __name__ == '__main__':
    wait_for_service(embedding_service_host, embedding_service_port)
    wait_for_service(nexus_service_host, nexus_service_port)

    while True:
        # get recent memories
        payload = {'lower_bound': time() - tempo, 'upper_bound': time()}
        recent = nexus_bound(payload)
        lines = [i['content'] for i in recent]
        textblock = ' '.join(lines)
        # TODO get relevant older memories too
        # COGNITIVE CONTROL - task selection, task switching (prioritization)
        # Am I performing well? Am I achieving my highest self? (heuristic imperatives, identity, etc)
        # Are all the microservices playing nice? Are our decisions and thoughts aligned?
        # Are we focused on the the right things? Task selection and task switching
        prompt = open_file('prompt_analyze.txt').replace('<<LOGS>>', textblock)
        analysis = gpt3_completion(prompt)
        save_and_send(analysis, content_prefix, 'analysis')
        # wait
        sleep(tempo)
