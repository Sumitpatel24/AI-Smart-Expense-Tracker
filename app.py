from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from io import BytesIO
from flask import send_file
from flask import make_response
import re
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "expense_tracker_secret"

app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'sumitpatel05'
app.config['MYSQL_DB'] = 'expense_tracker'

mysql = MySQL(app)

@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        # Password Validation

        if not re.match(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$',
            password
        ):

            flash(
                "Password must contain uppercase, lowercase, number and special character",
                "danger"
            )

            return redirect('/register')

        cur = mysql.connection.cursor()

        # Username Check

        cur.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        existing_user = cur.fetchone()

        if existing_user:

            flash("Username already exists", "danger")

            cur.close()

            return redirect('/register')

        # Email Check

        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        existing_email = cur.fetchone()

        if existing_email:

            flash("Email already registered", "danger")

            cur.close()

            return redirect('/register')

        # Insert User

        cur.execute(
        """
       INSERT INTO users
       (username,email,password)
       VALUES(%s,%s,%s) 
       """,
      (username,email,hashed_password)
       )

        mysql.connection.commit()

        cur.close()

        flash("Registration Successful", "success")

        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        user = cur.fetchone()

        cur.close()

        if user and check_password_hash(user[3], password):

            session['user'] = username

            flash("Login Successful", "success")

            return redirect('/dashboard')

        else:

            flash("Invalid Username or Password", "danger")

            return redirect('/login')

    return render_template('login.html')
@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # User ID

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user = cur.fetchone()

    if not user:
        cur.close()
        return redirect('/login')

    user_id = user[0]

    # Total Expense

    cur.execute(
        "SELECT IFNULL(SUM(amount),0) FROM expenses WHERE user_id=%s",
        (user_id,)
    )

    total_expense = float(cur.fetchone()[0])

    # Top Category

    cur.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id=%s
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
    """, (user_id,))

    top_category = cur.fetchone()

    # Highest / Lowest / Average

    cur.execute("""
        SELECT
        MAX(amount),
        MIN(amount),
        AVG(amount)
        FROM expenses
        WHERE user_id=%s
    """, (user_id,))

    stats = cur.fetchone()

    highest_expense = stats[0] or 0
    lowest_expense = stats[1] or 0
    average_expense = round(stats[2] or 0, 2)

    # Total Transactions

    cur.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id=%s",
        (user_id,)
    )

    total_transactions = cur.fetchone()[0]

    # Total Categories

    cur.execute(
        "SELECT COUNT(DISTINCT category) FROM expenses WHERE user_id=%s",
        (user_id,)
    )

    total_categories = cur.fetchone()[0]

    # Pie Chart Data

    cur.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=%s
        GROUP BY category
    """, (user_id,))

    chart_data = cur.fetchall()

    # Monthly Expense Data

    cur.execute("""
        SELECT MONTH(expense_date), SUM(amount)
        FROM expenses
        WHERE user_id=%s
        GROUP BY MONTH(expense_date)
        ORDER BY MONTH(expense_date)
    """, (user_id,))

    monthly_data = cur.fetchall()
     
    # Budget

    cur.execute("""
        SELECT monthly_budget
        FROM budgets
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))

    budget_row = cur.fetchone()

    budget = 0

    if budget_row:
        budget = float(budget_row[0])

    # Remaining Budget

    remaining = budget - total_expense

   # AI Spending Insights

    if total_transactions == 0:

     ai_message = "Add expenses to get AI insights."

    elif budget > 0 and total_expense > budget:

     if top_category:

        ai_message = (
            f"Your highest spending category is {top_category[0]} "
            f"with ₹{top_category[1]:.2f} spent. "
            f"You exceeded your budget by ₹{abs(remaining):.2f}."
        )

     else:

        ai_message = (
            f"You exceeded your budget by ₹{abs(remaining):.2f}."
        )
    
    elif budget > 0 and remaining <= budget * 0.2:

     ai_message = (
        f"Only ₹{remaining:.2f} budget remains. "
        "Spend carefully for the rest of the month."
    )

    elif top_category:

     ai_message = (
        f"Most of your spending is on {top_category[0]}. "
        "Consider reviewing this category."
    )

    else:

     ai_message = "Your spending looks balanced."
    
# Today's Expense

    cur.execute("""
     SELECT IFNULL(SUM(amount),0)
     FROM expenses
     WHERE user_id=%s
     AND expense_date = CURDATE()
     """, (user_id,))

    today_expense = float(cur.fetchone()[0])


   # This Month Expense

    cur.execute("""
     SELECT IFNULL(SUM(amount),0)
     FROM expenses
     WHERE user_id=%s
     AND MONTH(expense_date)=MONTH(CURDATE())
     AND YEAR(expense_date)=YEAR(CURDATE())
     """, (user_id,))

    month_expense = float(cur.fetchone()[0])


# This Week Expense

    cur.execute("""
    SELECT IFNULL(SUM(amount),0)
    FROM expenses
    WHERE user_id=%s
    AND YEARWEEK(expense_date,1)=YEARWEEK(CURDATE(),1)
    """, (user_id,))

    week_expense = float(cur.fetchone()[0])

    # Recent Transactions

    cur.execute("""
        SELECT amount,
        category,
        expense_date
        FROM expenses
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 5
        """, (user_id,))

    recent_expenses = cur.fetchall()

    cur.close()

    return render_template(
        'dashboard.html',
        username=session['user'],
        total_expense=total_expense,
        total_transactions=total_transactions,
        total_categories=total_categories,
        chart_data=chart_data,
        monthly_data=monthly_data,
        budget=budget,
        remaining=remaining,
        top_category=top_category,
        highest_expense=highest_expense,
        lowest_expense=lowest_expense,
        average_expense=average_expense,
        recent_expenses=recent_expenses,
        today_expense=today_expense,
        week_expense=week_expense,
        month_expense=month_expense,
        ai_message=ai_message
    )


@app.route('/logout')
def logout():

    session.clear()

    flash(
        "Logged Out Successfully",
        "success"
    )

    return redirect('/login')

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():

    if 'user' not in session:

        return redirect('/login')

    if request.method == 'POST':

        try:

            amount = float(request.form['amount'])

            if amount <= 0:

                flash(
                    "Amount must be greater than 0",
                    "danger"
                )

                return redirect('/add_expense')

            category = request.form['category']

            # Custom Category

            if category == "Other":

                custom_category = request.form[
                    'custom_category'
                ].strip()

                if not custom_category:

                    flash(
                        "Please enter custom category",
                        "danger"
                    )

                    return redirect('/add_expense')

                category = custom_category

            description = request.form['description']

            expense_date = request.form['expense_date']

            cur = mysql.connection.cursor()

            cur.execute(
                """
                SELECT id
                FROM users
                WHERE username=%s
                """,
                (session['user'],)
            )

            user = cur.fetchone()

            user_id = user[0]

            cur.execute(
                """
                INSERT INTO expenses
                (
                    user_id,
                    amount,
                    category,
                    description,
                    expense_date
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    user_id,
                    amount,
                    category,
                    description,
                    expense_date
                )
            )

            mysql.connection.commit()

            cur.close()

            flash(
                "Expense Added Successfully",
                "success"
            )

            return redirect('/dashboard')

        except Exception as e:

            flash(
                f"Error: {str(e)}",
                "danger"
            )

            return redirect('/add_expense')

    return render_template(
        'add_expense.html'
    )
@app.route('/expenses')
def expenses():

    if 'user' not in session:
        return redirect('/login')

    keyword = request.args.get('keyword', '')
    category = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user = cur.fetchone()
    user_id = user[0]

    query = """
        SELECT id, amount, category,
               description, expense_date
        FROM expenses
        WHERE user_id=%s
    """

    values = [user_id]

    if keyword:
        query += " AND description LIKE %s"
        values.append(f"%{keyword}%")

    if category:
        query += " AND category=%s"
        values.append(category)

    if start_date and end_date:
        query += " AND expense_date BETWEEN %s AND %s"
        values.append(start_date)
        values.append(end_date)

    query += " ORDER BY expense_date DESC"

    cur.execute(query, tuple(values))

    expenses = cur.fetchall()

    cur.close()

    return render_template(
        'expenses.html',
        expenses=expenses
    )

@app.route('/edit_expense/<int:id>', methods=['GET','POST'])
def edit_expense(id):

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    if request.method == 'POST':

        amount = request.form['amount']
        category = request.form['category']
        description = request.form['description']
        expense_date = request.form['expense_date']

        cur.execute(
            """
            UPDATE expenses
            SET amount=%s,
                category=%s,
                description=%s,
                expense_date=%s
            WHERE id=%s
            """,
            (amount, category, description, expense_date, id)
        )

        mysql.connection.commit()

        cur.close()

        flash("Expense Updated Successfully", "success")

        return redirect('/expenses')

    cur.execute(
        "SELECT * FROM expenses WHERE id=%s",
        (id,)
    )

    expense = cur.fetchone()

    cur.close()

    return render_template(
        'edit_expense.html',
        expense=expense
    )

@app.route('/delete_expense/<int:id>')
def delete_expense(id):

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute(
        "DELETE FROM expenses WHERE id=%s",
        (id,)
    )

    mysql.connection.commit()

    cur.close()

    flash("Expense Deleted Successfully", "success")

    return redirect('/expenses')

@app.route('/budget', methods=['GET', 'POST'])
def budget():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user_id = cur.fetchone()[0]

    if request.method == 'POST':

        budget_amount = request.form['budget']

        # Check existing budget

        cur.execute(
            "SELECT * FROM budgets WHERE user_id=%s",
            (user_id,)
        )

        existing_budget = cur.fetchone()

        if existing_budget:

            # Update Budget

            cur.execute(
                """
                UPDATE budgets
                SET monthly_budget=%s
                WHERE user_id=%s
                """,
                (budget_amount, user_id)
            )

        else:

            # Insert Budget

            cur.execute(
                """
                INSERT INTO budgets(user_id, monthly_budget)
                VALUES(%s,%s)
                """,
                (user_id, budget_amount)
            )

        mysql.connection.commit()

        cur.close()

        return redirect('/dashboard')

    cur.close()

    return render_template('budget.html')

@app.route('/download_report')
def download_report():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user_id = cur.fetchone()[0]

    cur.execute("""
        SELECT category,
               amount,
               description,
               expense_date
        FROM expenses
        WHERE user_id=%s
    """, (user_id,))

    expenses = cur.fetchall()

    response = make_response()

    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        'attachment; filename=Expense_Report.pdf'
    )

    pdf = canvas.Canvas(response.stream)

    pdf.setTitle("Expense Report")

    pdf.drawString(
        50,
        800,
        "Expense Report"
    )

    y = 760

    for expense in expenses:

        line = (
            f"{expense[0]} | "
            f"₹{expense[1]} | "
            f"{expense[2]} | "
            f"{expense[3]}"
        )

        pdf.drawString(50, y, line)

        y -= 20

    pdf.save()

    return response

@app.route('/search')
def search():

    if 'user' not in session:
        return redirect('/login')

    keyword = request.args.get('keyword', '')

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user_id = cur.fetchone()[0]

    cur.execute("""
        SELECT *
        FROM expenses
        WHERE user_id=%s
        AND category LIKE %s
    """, (user_id, f"%{keyword}%"))

    expenses = cur.fetchall()

    return render_template(
        'expenses.html',
        expenses=expenses
    )
@app.route('/filter')
def filter_expenses():

    if 'user' not in session:
        return redirect('/login')

    start = request.args.get('start_date')
    end = request.args.get('end_date')

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user_id = cur.fetchone()[0]

    # Agar date select nahi ki gayi
    if not start or not end:

        cur.execute(
            "SELECT * FROM expenses WHERE user_id=%s",
            (user_id,)
        )

    else:

        cur.execute("""
            SELECT *
            FROM expenses
            WHERE user_id=%s
            AND expense_date BETWEEN %s AND %s
        """, (user_id, start, end))

    expenses = cur.fetchall()

    cur.close()

    return render_template(
        'expenses.html',
        expenses=expenses
    )
@app.route('/export_excel')
def export_excel():

    if 'user' not in session:
     return redirect('/login')

    from openpyxl import Workbook
    from openpyxl.styles import Font
    from io import BytesIO
    from flask import send_file

    cur = mysql.connection.cursor()

    cur.execute(
     "SELECT id FROM users WHERE username=%s",
    (session['user'],)
    )

    user_id = cur.fetchone()[0]

    cur.execute("""
    SELECT amount,
           category,
           description,
           expense_date
    FROM expenses
    WHERE user_id=%s
    """, (user_id,))

    expenses = cur.fetchall()

    wb = Workbook()
    ws = wb.active

    ws.title = "Expenses"

   # Headers

    headers = [
    "Amount",
    "Category",
    "Description",
    "Date"
    ]

    for col_num, header in enumerate(headers, 1):

     cell = ws.cell(row=1, column=col_num)
 
     cell.value = header

     cell.font = Font(bold=True)

    # Data

    for row_num, expense in enumerate(expenses, start=2):

     ws.cell(row=row_num, column=1, value=expense[0])
     ws.cell(row=row_num, column=2, value=expense[1])
     ws.cell(row=row_num, column=3, value=expense[2])
     ws.cell(row=row_num, column=4, value=expense[3])

    # Column Width

    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 35
    ws.column_dimensions['D'].width = 20

    # Date Format

    for row in ws.iter_rows(min_row=2, max_col=4):

      row[3].number_format = 'DD-MM-YYYY'

    file_stream = BytesIO()

    wb.save(file_stream)

    file_stream.seek(0)

    return send_file(
     file_stream,
     as_attachment=True,
     download_name="Expense_Report.xlsx",
     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route('/profile')
def profile():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # User Details
    cur.execute(
        """
        SELECT id, username, email
        FROM users
        WHERE username=%s
        """,
        (session['user'],)
    )

    user = cur.fetchone()

    user_id = user[0]

    # Total Expense
    cur.execute(
        """
        SELECT IFNULL(SUM(amount),0)
        FROM expenses
        WHERE user_id=%s
        """,
        (user_id,)
    )

    total_expense = float(cur.fetchone()[0])

    # Total Transactions
    cur.execute(
        """
        SELECT COUNT(*)
        FROM expenses
        WHERE user_id=%s
        """,
        (user_id,)
    )

    total_transactions = cur.fetchone()[0]

    # Budget
    cur.execute(
        """
        SELECT monthly_budget
        FROM budgets
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,)
    )

    budget_row = cur.fetchone()

    budget = 0

    if budget_row:
        budget = float(budget_row[0])

    cur.close()

    return render_template(
        'profile.html',
        user=user,
        total_expense=total_expense,
        total_transactions=total_transactions,
        budget=budget
    )

@app.route('/change_password', methods=['POST'])
def change_password():

    if 'user' not in session:
        return redirect('/login')

    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Confirm Password Check
    if new_password != confirm_password:
        return """
        <script>
        alert('New Password and Confirm Password do not match');
        window.location='/profile';
        </script>
        """

    # Current Password Check
    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT password
        FROM users
        WHERE username=%s
        """,
        (session['user'],)
    )

    db_password = cur.fetchone()[0]

    if current_password != db_password:
        return """
        <script>
        alert('Current Password Incorrect');
        window.location='/profile';
        </script>
        """

    # Strong Password Validation
    password_pattern = (
        r'^(?=.*[a-z])'
        r'(?=.*[A-Z])'
        r'(?=.*\d)'
        r'(?=.*[@$!%*?&])'
        r'[A-Za-z\d@$!%*?&]{8,}$'
    )

    if not re.match(password_pattern, new_password):
        return """
        <script>
        alert('Password must contain:\\n\\nMinimum 8 characters\\n1 Capital Letter\\n1 Small Letter\\n1 Number\\n1 Special Character');
        window.location='/profile';
        </script>
        """

    # Update Password
    cur.execute(
        """
        UPDATE users
        SET password=%s
        WHERE username=%s
        """,
        (new_password, session['user'])
    )

    mysql.connection.commit()

    cur.close()

    return """
    <script>
    alert('Password Changed Successfully');
    window.location='/profile';
    </script>
    """

@app.route('/delete_account')
def delete_account():

    if 'user' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['user'],)
    )

    user = cur.fetchone()

    if user:

        user_id = user[0]

        # Delete Expenses

        cur.execute(
            "DELETE FROM expenses WHERE user_id=%s",
            (user_id,)
        )

        # Delete Budget

        cur.execute(
            "DELETE FROM budgets WHERE user_id=%s",
            (user_id,)
        )

        # Delete User

        cur.execute(
            "DELETE FROM users WHERE id=%s",
            (user_id,)
        )

        mysql.connection.commit()

    cur.close()

    session.clear()

    flash(
        "Account Deleted Successfully",
        "success"
    )

    return redirect('/register')
@app.route('/toggle_theme')
def toggle_theme():

    if 'theme' not in session:

        session['theme'] = 'dark'

    if session['theme'] == 'dark':

        session['theme'] = 'light'

    else:

        session['theme'] = 'dark'

    return redirect(request.referrer)
if __name__ == '__main__':
    app.run(debug=True)