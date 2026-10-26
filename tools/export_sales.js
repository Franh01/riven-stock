const fs=require('fs');const path='W:/Proyectos personales (claude)/riven-stock/cloud/';
require('dns').setServers(['8.8.8.8']);
const env={};fs.readFileSync('W:/Proyectos personales (claude)/.secrets/atlas.env','utf8').split(/\r?\n/).forEach(l=>{const m=l.match(/^(\w+)=(.*)$/);if(m)env[m[1]]=m[2]});
const {MongoClient}=require(path+'node_modules/mongodb');
(async()=>{const uri=`mongodb+srv://${encodeURIComponent(env.ATLAS_DB_USER)}:${encodeURIComponent(env.ATLAS_DB_PASSWORD)}@${env.ATLAS_CLUSTER_HOST}/riven_stock`;
const c=await MongoClient.connect(uri,{serverSelectionTimeoutMS:20000});
const r=await c.db('riven_stock').collection('sales').find({suspect:{$exists:false}},{projection:{weapon:1,price:1,price_first:1,attrs:1,rolls:1,mr:1,rank:1,days_listed:1,confidence:1,detected_at:1}}).toArray();
fs.writeFileSync(process.argv[2],JSON.stringify(r));console.log(r.length);await c.close();})().catch(e=>console.log('ERR',e.message));
