const { MongoClient } = require("mongodb");

let client;

// La conexión se reutiliza entre invocaciones de la misma Lambda.
async function snapshots() {
  if (!client) {
    client = new MongoClient(process.env.MONGODB_URI, { maxPoolSize: 2, serverSelectionTimeoutMS: 8000 });
    await client.connect();
  }
  return client.db("riven_stock").collection("market_snapshots");
}

module.exports = { snapshots };
