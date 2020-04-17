import flask
import pymongo
import requests
from datetime import datetime
from random import randint
from time import time

app = flask.Flask(__name__)

mongo_client = pymongo.MongoClient('localhost', 27017)
pollsDB = mongo_client.pollsDB
polls = pollsDB.polls
poll_options = pollsDB.options

@app.route('/', methods=['GET'])
def home():
    return flask.render_template('index.html')

@app.route('/poll', methods=['POST'])
def create():
    form_data = dict(flask.request.form)
    poll = {k:v for k, v in form_data.items() if (not k.startswith('option'))}
    if 'expiry' not in poll:
        poll.pop('expiryHours')
    else:
        poll.pop('expiry')
        poll['expiryHours'] = int(poll['expiryHours'])
    if 'limit' not in poll:
        poll.pop('limitValue')
    else:
        poll.pop('limit')
        poll['limitValue'] = int(poll['limitValue'])
    poll['question'] = poll['question'].strip()
    poll['votes'] = 0
    poll['creationTime'] = int(time())
    while True:
        poll_id = randint(1,1000000)
        if polls.count_documents({'id': poll_id}) == 0:
            break
    poll['id'] = poll_id
    options = [{'id': poll_id, 'option': v.strip(), 'votes': 0} for k, v in
                form_data.items() if k.startswith('option') and v]
    op_num = 1
    for option in options:
        option['op_num'] = op_num
        op_num += 1
    polls.insert_one(poll)
    poll_options.insert_many(options)
    return flask.render_template('creating.html', poll_id=poll_id)

@app.route('/poll/<int:poll_id>/categorize', methods=['POST'])
def categorize(poll_id):
    poll = [_ for _ in polls.find({'id': poll_id}, {'_id': False})][0]
    options = [_ for _ in poll_options.find({'id': poll_id}, {'_id': False})]
    options_txt = poll['question']
    for option in options:
        options_txt += ' ' + option['option']
    category = requests.post(url='http://api.meaningcloud.com/class-1.1',
                             json={'key': 'f30037c59ff5341084d6555bf6bbfc18',
                                   'title':poll['question'], 'txt':options_txt,
                                   'model':'IAB_en'}).json()['category_list'][0]['code']
    subtopic = category.find('>')
    if subtopic != -1:
        category = category[:subtopic]
    polls.update_one({'id': poll_id}, {'$set': {'category': category}})
    return flask.Response(status=200)   

@app.route('/poll/<int:poll_id>', methods=['GET'])
def view(poll_id):
    currentTime = int(time())
    try:
        poll = [_ for _ in polls.find({'id': poll_id}, {'_id': False})][0]
    except:
        return flask.abort(404)
    options = [_ for _ in poll_options.find({'id': poll_id}, {'_id': False})]
    question = poll['question']
    votes = poll['votes']
    creationTime = poll['creationTime']
    if 'expiryHours' in poll:
        time_left = poll['expiryHours'] - (currentTime - creationTime)/3600
        time_left_m = int((time_left - int(time_left))*60)
        expired = 1 if time_left<=0 else 0
        expirable = 1
    else:
        time_left = -1
        time_left_m = -1
        expired = 0
        expirable = 0
    limited = 1 if 'limitValue' in poll and votes==poll['limitValue'] else 0
    options_text = ''
    for option in options:
        options_text += option['option'] + '█'
    options_text = options_text[:-1]
    if poll['category'] != 'Uncategorized':
        similar_polls = polls.find({'$and': [{'category': poll['category']}, {'private': {'$exists': False}}, {'id': {'$ne': poll['id']}}]}).sort('votes', -1)
        similar_polls = [_ for _ in similar_polls]
        similar = len(similar_polls)>0
        similar_data = []
        for simpoll in similar_polls:
            time_text = datetime.fromtimestamp(simpoll['creationTime']).strftime("Created on %A, %B %d, %Y at %#I:%M %p")
            similar_data.append('<div class="box" id="sim" onclick="goto('+ str(simpoll['id']) + \
                                ')"><p class="title is-4">'+ simpoll['question'] + \
                                '</p><p class="subtitle is-7">Votes: '+ str(simpoll['votes']) + \
                                '&nbsp;&nbsp;|&nbsp;&nbsp;'+ time_text + \
                                '</p></div>')
        similar_data = similar_data[:5]
    else:
        similar = False
        similar_data = []
    time_text = datetime.fromtimestamp(creationTime).strftime("Created on %A, %B %d, %Y at %#I:%M %p")
    return flask.render_template('poll.html', question=poll['question'], poll_id=poll_id,
                                  creationTime=creationTime*1000, limited=limited,
                                  expirable=expirable, expired=expired, time_left=time_left,
                                  numberOfOptions=len(options), options_text=options_text,
                                  votes=votes, expiry_h=int(time_left), expiry_m=time_left_m,
                                  similar=similar, similar_data=similar_data, time_text=time_text)

@app.route('/poll/<int:poll_id>/<int:option>', methods=['PATCH'])
def vote(poll_id, option):
    poll = [_ for _ in polls.find({'id': poll_id}, {'_id': False})][0]
    if 'limitValue' in poll and int(poll['votes'])>=int(poll['limitValue']):
        return flask.Response(status=400)
    polls.update_one({'id': poll_id}, {'$inc': {'votes': 1}})
    poll_options.update_one({'id': poll_id, 'op_num': option}, {'$inc': {'votes': 1}})
    return flask.Response('0', status=200)

@app.route('/poll/<int:poll_id>/results', methods=['GET'])
def results(poll_id):
    currentTime = int(time())
    try:
        poll = [_ for _ in polls.find({'id': poll_id}, {'_id': False})][0]
    except:
        return flask.abort(404)
    options = [_ for _ in poll_options.find({'id': poll_id}, {'_id': False})]
    question = poll['question']
    votes = poll['votes']
    creationTime = poll['creationTime']
    if 'expiryHours' in poll:
        time_left = poll['expiryHours'] - (currentTime - creationTime)/3600
        time_left_m = int((time_left - int(time_left))*60)
        expired = 1 if time_left<=0 else 0
        expirable = 1
    else:
        time_left = -1
        time_left_m = -1
        expired = 0
        expirable = 0
    limited = 1 if 'limitValue' in poll and votes==poll['limitValue'] else 0
    options_text = ''
    votes_text = ''
    for option in options:
        options_text += option['option'] + '█'
        votes_text += str(option['votes']) + '█'
    options_text = options_text[:-1]
    votes_text = votes_text[:-1]
    if poll['category'] != 'Uncategorized':
        similar_polls = polls.find({'$and': [{'category': poll['category']}, {'private': {'$exists': False}}, {'id': {'$ne': poll['id']}}]}).sort('votes', -1)
        similar_polls = [_ for _ in similar_polls]
        similar = len(similar_polls)>0
        similar_data = []
        for simpoll in similar_polls:
            time_text = datetime.fromtimestamp(simpoll['creationTime']).strftime("Created on %A, %B %d, %Y at %#I:%M %p")
            similar_data.append('<div class="box" id="sim" onclick="goto('+ str(simpoll['id']) + \
                                ')"><p class="title is-4">'+ simpoll['question'] + \
                                '</p><p class="subtitle is-7">Votes: '+ str(simpoll['votes']) + \
                                '&nbsp;&nbsp;|&nbsp;&nbsp;'+ time_text + \
                                '</p></div>')
        similar_data = similar_data[:5]
    else:
        similar = False
        similar_data = []
    time_text = datetime.fromtimestamp(creationTime).strftime("Created on %A, %B %d, %Y at %#I:%M %p")
    return flask.render_template('results.html', question=poll['question'], poll_id=poll_id,
                                  creationTime=creationTime*1000, limited=limited,
                                  expirable=expirable, expired=expired, time_left=time_left,
                                  numberOfOptions=len(options), options_text=options_text,
                                  votes=votes, votes_text=votes_text, expiry_h=int(time_left),
                                  expiry_m=time_left_m, time_text=time_text, similar=similar,
                                  similar_data=similar_data)

@app.route('/poll/<int:poll_id>/votes', methods=['GET'])
def votes(poll_id):
    options = [_ for _ in poll_options.find({'id': poll_id}, {'_id': False})]
    votes_text = ''
    for option in options:
        votes_text += str(option['votes']) + '█'
    votes_text = votes_text[:-1]
    return votes_text, 200

@app.route('/popular', methods=['GET'])
def popular():
    popular_polls = [_ for _ in polls.find({'private': {'$exists': False}}, {'_id': False}).sort('votes', -1)][:11]
    polls_data = []
    for poll in popular_polls:
        time_text = datetime.fromtimestamp(poll['creationTime']).strftime("Created on %A, %B %d, %Y at %#I:%M %p")
        polls_data.append('<div class="box" onclick="goto('+ str(poll['id']) + \
                      ')"><p class="title is-4">'+ poll['question'] + \
                      '</p><p class="subtitle is-7">Votes: '+ str(poll['votes']) + \
                      '&nbsp;&nbsp;|&nbsp;&nbsp;'+ time_text + \
                      '</p></div>')
    return flask.render_template('popular.html', polls_data=polls_data)

@app.route('/recent', methods=['GET'])
def recent():
    recent_polls = [_ for _ in polls.find({'private': {'$exists': False}}, {'_id': False}).sort('creationTime', -1)][:11]
    polls_data = []
    for poll in recent_polls:
        time_text = datetime.fromtimestamp(poll['creationTime']).strftime("Created on %A, %B %d, %Y at %#I:%M %p")
        polls_data.append('<div class="box" onclick="goto('+ str(poll['id']) + \
                      ')"><p class="title is-4">'+ poll['question'] + \
                      '</p><p class="subtitle is-7">Votes: '+ str(poll['votes']) + \
                      '&nbsp;&nbsp;|&nbsp;&nbsp;'+ time_text + \
                      '</p></div>')
    return flask.render_template('recent.html', polls_data=polls_data)

@app.route('/stats', methods=['GET'])
def stats():
    poll_count = polls.count_documents({})
    private_polls = polls.count_documents({'private': {'$exists': True}})
    total_votes = 0
    for poll in polls.find({}):
        total_votes += int(poll['votes'])
    try:
        top_poll = [_ for _ in polls.find({'private': {'$exists': False}}, {'_id': False}).sort('votes', -1)][0]
    except:
        return flask.render_template('statistics.html', poll_count=poll_count, public_polls=poll_count-private_polls,
                                 private_polls=private_polls, total_votes=total_votes)
    return flask.render_template('statistics.html', top_poll_question=top_poll['question'],
                                 top_poll_votes=top_poll['votes'], top_poll_id=top_poll['id'],
                                 poll_count=poll_count, public_polls=poll_count-private_polls,
                                 private_polls=private_polls, total_votes=total_votes)


@app.route('/about', methods=['GET'])
def about():
    return flask.render_template('about.html')

@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404

if __name__ == '__main__':
    app.run(host='localhost', port='80', debug=True)
