from flask import session, request
import pymysql
import os


def get_db_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_all_clients():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ClientID, FirstName, LastName FROM Client")
            return cur.fetchall()


def get_client_by_id(client_id):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ClientID, FirstName, LastName, Email FROM Client WHERE ClientID = %s",
                (client_id,),
            )
            return cur.fetchone()


def get_client_rentals(client_id):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM Rental WHERE ClientID = %s ORDER BY RentalDate",
                (client_id,),
            )
            return cur.fetchall()


def book_rental():
    client_id = session.get("client_id")
    boat_id = request.form.get("boat_id")
    rental_date = request.form.get("rental_date")
    rental_end_date = request.form.get("rental_end_date")

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO Rental (ClientID, BoatID, RentalDate, RentalEndDate, PaymentStatus)
                VALUES (%s, %s, %s, %s, 'Pending')
                """,
                (client_id, boat_id, rental_date, rental_end_date),
            )
            conn.commit()
