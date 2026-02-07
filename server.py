from flask import Flask, Response

app = Flask(__name__)

@app.route("/", methods=["POST"])
def voice():
    return Response("""
<Response>
  <Say voice="alice">Test call</Say>
  <Dial>+13237440002</Dial>
</Response>
""", mimetype="text/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
