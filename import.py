import os
import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    fin = csv.reader(open("books.csv", "r"))
    next(fin)
    for ibsn, title, author, year in fin:
        db.execute("INSERT INTO books (ibsn, title, author, year) VALUES (:ibsn, :title, :author, :year);",
        {"ibsn":ibsn, "title":title, "author":author, "year":year})
    db.commit()


if __name__ == "__main__":
    main()
