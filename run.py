from app import create_app

app = create_app()  # This is what gunicorn needs

if __name__ == '__main__':
    app.run(debug=True)
