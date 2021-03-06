from utils import load_config
from logger import setup_log
from flask import Flask, request, render_template, session, redirect, url_for
from flask import jsonify
from utils import mysql

config = load_config()
logger = setup_log(__name__)
app = Flask(__name__)
app.config['SECRET_KEY'] = '470581985@qq.com'
mysql = mysql(config['mysql'])


@app.route("/")
def root():
    """
    主页
    :return: home.html
    """
    login, userid = False, ''
    if 'userid' in session:
        login, userid = True, session['userid']
    # 热门书籍
    hot_books = []
    # sql: SELECT BookID,sum(Rating) as score FROM Book.Bookrating group by BookID order by score desc limit 10;
    sql = "SELECT BookTitle, BookAuthor ,BookID, ImageM FROM Books where BookID = '" + \
          "' or BookID = '".join(config['bookid']) + "'"

    try:
        hot_books = mysql.fetchall_db(sql)
        hot_books = [[v for k, v in row.items()] for row in hot_books]

    except Exception as e:
        logger.exception("select hot books error: {}".format(e))

    return render_template('Index.html',
                           login=login,
                           books=hot_books,
                           useid=userid)


@app.route("/recommend")
def recommend():
    """
    推荐页面
    :return: Index.html
    """
    login, userid, error = False, '', False
    if 'userid' in session:
        login, userid = True, session['userid']
    # 推荐书籍
    recommend_books = []
    if login:
        sql = """select e.BookTitle,
                       e.BookAuthor,
                       e.BookID,
                       e.ImageM
                       from Books e
                inner join (select  c.BookID,
                                    sum(c.Rating) as score  
                            from (select UserID,BookID,Rating from Bookrating where Rating != 0
                                limit {0}) c 
                            inner join (select UserID 
                                        from (select UserID,BookID from Bookrating where Rating != 0
                                        limit {0}) a 
                                        inner join (select BookID from Booktuijian where UserID='{1}') b
                                        on a.BookID=b.BookID ) d
                            on c.UserID=d.UserID
                            group by c.BookID 
                            order by score desc 
                            limit 10) f
                on e.BookID = f.BookID""".format(config['limit'],session['userid'])
        try:
            recommend_books = mysql.fetchall_db(sql)
            recommend_books = [[v for k, v in row.items()] for row in recommend_books]
            
        except Exception as e:
            error = True
            logger.exception("select recommend books error: {}".format(e))
    return render_template('Index.html',
                           login=login,
                           books=recommend_books,
                           useid=userid,
                           error=error)


@app.route("/loginForm")
def loginForm():
    """
    跳转登录页
    :return: Login.html
    """
    if 'userid' in session:
        return redirect(url_for('root'))
    else:
        return render_template('Login.html', error='')


@app.route("/registerationForm")
def registrationForm():
    """
    跳转注册页
    :return: Register.html
    """
    return render_template("Register.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    注册
    :return: Register.html
    """
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            age = request.form['age']

            try:
                sql = "insert into User (UserID,Location,Age) values ('{}','{}','{}')".format(username, password, age)
                mysql.exe(sql)
                logger.info("username:{},password:{},age:{} register success".format(username, password, age))
            except Exception as e:
                mysql.rollback()
                logger.exception("username:{},password:{},age:{} register filed".format(username, password, age))
            return render_template('Login.html')
    except Exception as e:
        logger.exception("register function error: {}".format(e))
        return render_template('Register.html', error='注册出错')


def is_valid(username, password):
    """
    登录验证
    :param username: 用户名
    :param password: 密码
    :return: True/False
    """
    try:
        sql = "SELECT UserID, Location as Username FROM User where UserID='{}' and Location ='{}'".format(username,
                                                                                                          password)
        result = mysql.fetchone_db(sql)

        if result:
            logger.info('username:{},password:{}: has login success'.format(username, password))
            return True
        else:
            logger.info('username:{},password:{}: has login filed'.format(username, password))
            return False
    except Exception as e:
        logger.exception('username:{},password:{}: has login error'.format(username, password))
        return False


@app.route("/login", methods=['POST', 'GET'])
def login():
    """
    登录页提交
    :return: Login.html
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if is_valid(username, password):
            session['userid'] = username
            return redirect(url_for('root'))
        else:
            error = '账号密码输入错误'
            return render_template('Login.html', error=error)


@app.route("/logout")
def logout():
    """
    退出登录，注销
    :return: root
    """
    session.pop('userid', None)
    return redirect(url_for('root'))


@app.route("/order", methods=['POST', 'GET'])
def order():
    """
    书单
    :return: Order.html
    """
    if 'userid' not in session:
        return redirect(url_for('loginForm'))

    return render_template("Order.html")

def update_recommend_book(UserID,BookID):
    """
    更新推荐数据
    """

    sql = '''SELECT score FROM Booktuijian WHERE UserID="{0}" and BookID="{1}"'''.format(UserID,BookID)
    score = mysql.fetchone_db(sql)
    if score:
        score = score['score']
        score += 1
        sql =  '''UPDATE Booktuijian SET score='{2}' WHERE UserID="{0}" and BookID="{1}"  '''.format(UserID,BookID,int(score))
        logger.info("update_recommend_book, sql:{}".format(sql))
        mysql.exe(sql)
    else:
        score = 1
        sql= ''' insert into Booktuijian (UserID,BookID,score) values ('{0}','{1}','{2}') '''.format(UserID,BookID,int(score))
        logger.info("update_recommend_book, sql:{}".format(sql))
        mysql.exe(sql)

@app.route("/bookinfo", methods=['POST', 'GET'])
def bookinfo():
    """
    书籍详情
    :return: BookInfo.html
    """
    # 获取用户IP
    if 'userid' not in session:
        userid = request.remote_addr
    else:
        userid = session['userid']
    try:
        if request.method == 'GET':
            ID = request.args.get('bookid')
            sql = """SELECT BookTitle,
                            BookID,
                            PubilcationYear,
                            BookAuthor,
                            ImageM from Books where BookID="{}" """.format(ID)
            book_info = mysql.fetchall_db(sql)
            book_info = [v for k, v in book_info[0].items()]
            update_recommend_book(userid,ID)
    except Exception as e:
        logger.exception("select book info error: {}".format(e))
    return render_template('BookInfo.html', book_info=book_info)


@app.route("/user", methods=['POST', 'GET'])
def user():
    """
    个人信息
    :return: UserInfo.html
    """
    if 'userid' not in session:
        return redirect(url_for('loginForm'))
    return render_template('UserInfo.html')


@app.route("/search", methods=['POST', 'GET'])
def search():
    """
    书籍检索
    :return: Search.html
    """
    keyword, search_books = "", []
    try:
        if request.method == 'GET':
            keyword = request.values.get('keyword')
            keyword = keyword.strip()
            sql = "SELECT BookTitle, BookAuthor ,BookID, ImageM from Books where BookTitle like '%{}%' limit 20".format(
                keyword)
            search_books = mysql.fetchall_db(sql)
            search_books = [[v for k, v in row.items()] for row in search_books]
    except Exception as e:
        logger.exception("select search books error: {}".format(e))
    return render_template("Search.html", key=keyword, books=search_books)






if __name__ == '__main__':
    app.run(debug=True, port=8080)
