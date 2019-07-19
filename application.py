import os
import requests
import bcrypt

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        session["logged_in"] = False # This is because when the user is logged in, the log in button becomes the log out button.
        session["user_id"] = None
        return render_template("index.html", alert="You have sucessfully logged out.")
    else:
        if request.method == "POST":

            username = request.form.get("username")
            password = request.form.get("password")

            # Check that the User exists via username
            if db.execute("SELECT * FROM users WHERE username = :username", {"username" : username}).rowcount == 0:
                return render_template("login.html", alert="The account you're trying to access does not exist.")
            else:

                # Check that the password matches with the user account with the username
                user = db.execute("SELECT * FROM users WHERE username = :username", {"username" : username}).fetchone()
                if user is None:
                    return render_template("login.html", alert="The account you are trying to access does not exist.")
                else:
                    if bcrypt.checkpw(password.encode('utf8'), user.passhash.encode('utf8')):
                        print("correct password")
                        session["logged_in"] = True
                        session["user_id"] = user.id
                        return render_template("search.html", alert="Welcome, " + username)

                    else:
                        return render_template("login.html", alert="Incorrect password.")


        else:
            return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("logged_in"):
        return render_template("index.html", message="You're already logged in!")
    else:

        if request.method == "POST":
            # users = db.execute("SELECT * FROM users").fetchall()
            username = request.form.get("username")
            password = request.form.get("password")

            if type(password) is not None and len(password) > 1 and type(username) is not None and len(username) > 1:

                # Generate a hash for the given password
                hashed = bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())

                # Check to see if the username is available
                if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount == 0:
                    db.execute("INSERT INTO users (username, passhash) VALUES (:username, :passhash)", {"username" : username, "passhash" : hashed.decode('utf8')})
                    db.commit()
                else:
                    return render_template("index.html", message="Error! The Username you entered was not available.") # Change this to a notification on the register page later...

                # Render the homepage with a new message
                return render_template("index.html", message="Success! You have been registered.")

            else:
                return render_template("register.html", message="Your username or password must be longer than that!")

        else:
            return render_template("register.html")


@app.route("/books", methods=["GET", "POST"])
def books():
    books = db.execute("SELECT * FROM books").fetchall()
    return render_template("books.html", books=books)


@app.route("/books/<book_title>", methods=["GET", "POST"])
def book(book_title):

    reviews = db.execute("SELECT * FROM reviews").fetchall()
    book = db.execute("SELECT * FROM books WHERE book_title = :book_title", {"book_title":book_title}).fetchone()

    if book is None:
        return render_template("index.html", message="Looks like we don't have a page for that book yet.")

    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "QzYXcuEKWBsDhDzdKWDuw", "isbns": book.ibsn}) # Yeah, I know the B and N are swapped
                                                                                                                                         # but I already exported the books.
    good_average_rating = res.json()["books"][0]["average_rating"]
    good_review_number = res.json()["books"][0]["work_ratings_count"]

    if request.method == "GET":

        if session["logged_in"]:
            poster = db.execute("SELECT * FROM users WHERE id = :id", {"id":session["user_id"]}).fetchone()

            if db.execute("SELECT * FROM reviews WHERE author = :author AND book = :book", {"author":poster.username, "book":book.book_title}).rowcount == 0:
                return render_template("book.html", book=book, reviews=reviews, made_review=False, good_average_rating=good_average_rating, good_review_number=good_review_number)

        return render_template("book.html", book=book, made_review=True, reviews=reviews, good_average_rating=good_average_rating, good_review_number=good_review_number)

    else:

        stars = request.form.get("stars")
        review = request.form.get("review")

        if session["logged_in"]:
            poster = db.execute("SELECT * FROM users WHERE id = :id", {"id":session["user_id"]}).fetchone()

            if poster is None:
                return render_template("book.html", message="Something has gone terribly, terribly wrong.", book=book, made_review=True, reviews=reviews, good_average_rating=good_average_rating, good_review_number=good_review_number)

            if db.execute("SELECT * FROM reviews WHERE author = :author AND book = :book", {"author":poster.username, "book":book.book_title}).rowcount == 0:
                db.execute("INSERT INTO reviews (author, rating, comment, book) VALUES (:author, :rating, :comment, :book)", {"author":poster.username, "rating":stars, "comment":review, "book":book.book_title})
                db.commit()

        reviews = db.execute("SELECT * FROM reviews").fetchall()
        return render_template("book.html", book=book, made_review=True, reviews=reviews, good_average_rating=good_average_rating, good_review_number=good_review_number)



@app.route("/api/<isbn>", methods=["GET", "POST"])
def api(isbn):
    book = db.execute("SELECT * FROM books WHERE ibsn = :isbn", {"isbn":isbn}).fetchone()
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "QzYXcuEKWBsDhDzdKWDuw", "isbns": book.ibsn})
    good_average_rating = res.json()["books"][0]["average_rating"]
    good_review_number = res.json()["books"][0]["work_ratings_count"]

    return jsonify({
              "book_title": book.book_title,
              "author": book.author,
              "year": book.year,
              "isbn": book.ibsn,
              "review_count": good_review_number,
              "average_score": good_average_rating
          })

@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        search = "%" + request.form.get("search") + "%"

        results = db.execute("SELECT * FROM books WHERE LOWER(ibsn) LIKE LOWER(:search) OR LOWER(book_title) LIKE LOWER(:search) OR LOWER(author) LIKE LOWER(:search)",{"search": search}).fetchall()

        if results == []:
            return render_template("search.html", results=results)




        return render_template("search.html", search=search[1:len(search)-1], results=results)
    else:
        return render_template("search.html")
