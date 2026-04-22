# GPS-data-on-RaspberryPi-Pico-W
This is simple gadget that can represent your GPS data as "how far are you and azimut". I build it for my wife, to know how far I am when I worked as truck driver. You can use it in another way, you can know how far you are from home.

You need to prepare VPS server with linux (ubuntu in my setup)
-Then update by:
sudo apt update && sudo apt upgrade -y

-Install JAVA (JRE):
sudo apt install unzip default-jre -y

-Install TRACCAR SERVER:
https://www.traccar.org/install-digitalocean/

-Start TRACCAR and enable autorun:
sudo systemctl start traccar
sudo systemctl enable traccar

-You need to open ports on you VPS Server (8082,5023,5013,3000,22), and run it in iptables:
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8082 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5023 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5013 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 3000 -j ACCEPT
sudo netfilter-persistent save

or

sudo iptables -I INPUT 1 -p tcp --dport 8082 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 5023 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 5013 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 3000 -j ACCEPT

-You can check TRACCAR webapp http:/YOUR.SERVER.IP:8082
admin
admin

-PostgreSQL is better:
sudo apt update
sudo apt install postgresql postgresql-contrib -y

-Make new data base:
sudo -u postgres psql -c "CREATE DATABASE traccar;"
sudo -u postgres psql -c "CREATE USER traccar WITH PASSWORD 'yourpassword';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE traccar TO traccar;"
sudo -u postgres psql -d traccar -c "GRANT ALL ON SCHEMA public TO traccar;"

-Edit traccar.xml:
sudo nano /opt/traccar/conf/traccar.xml

delete:
    <entry key='database.driver'>org.h2.Driver</entry>
    <entry key='database.url'>jdbc:h2:./data/database</entry>
    <entry key='database.user'>sa</entry>
    <entry key='database.password'></entry>

paste:
    <entry key='database.driver'>org.postgresql.Driver</entry>
    <entry key='database.url'>jdbc:postgresql://127.0.0.1:5432/traccar</entry>
    <entry key='database.user'>traccar</entry>
    <entry key='database.password'>yourpassword</entry>

for ignore NULL ISLAND:
paste before </properties>
    <entry key='filter.enable'>true</entry>
    <entry key='filter.zero'>true</entry>
    
-Restart TRACCAR:
sudo systemctl restart traccar

-Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x
sudo -E bash -sudo apt install -y nodejs

node -v

-make API:
cd ~
mkdir my-api-gps
cd my-api-gps
npm init -y
npm install express pg cors

nano server.js

Paste:
--------------------------------------------------------------------------------------------
 
const express = require('express');
const { Pool } = require('pg');
const cors = require('cors');

const app = express();
const port = 3000;

app.use(cors());
app.use(express.json());

// Config
const pool = new Pool({
  user: 'traccar',
  host: '127.0.0.1',
  database: 'traccar',
  password: 'yourpassword', // CHANGE IT!!
  port: 5432,
});

// Endpoint 1: Last position
app.get('/api/pozycja/:deviceId', async (req, res) => {
  const deviceId = req.params.deviceId;
  try {
    const result = await pool.query(
      `SELECT latitude, longitude, speed, fixtime 
       FROM tc_positions 
       WHERE deviceid = $1 
       ORDER BY fixtime DESC LIMIT 1`,
      [deviceId]
    );
    if (result.rows.length === 0) return res.status(404).json({ error: 'Brak danych' });
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Błąd bazy danych' });
  }
});

// Endpoint 2: Last 24h
app.get('/api/trasa/:deviceId', async (req, res) => {
  const deviceId = req.params.deviceId;
  try {
    const result = await pool.query(
      `SELECT latitude, longitude, speed, fixtime 
       FROM tc_positions 
       WHERE deviceid = $1 
       AND fixtime >= NOW() - INTERVAL '24 HOURS'
       ORDER BY fixtime ASC`,
      [deviceId]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'ERROR' });
  }
});

app.listen(port, () => {
  console.log(`API works on port ${port}`);
});


--------------------------------------------------------------------------------------------

-Install PM2:
sudo npm install -g pm2

-Start API:
pm2 start server.js --name "api-gps"
pm2 save
pm2 startup

