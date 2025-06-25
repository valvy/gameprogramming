const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const tileSize = canvas.width / 20;
const winnerElem = document.getElementById("winner");

function draw(state) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Grid tekenen
    ctx.strokeStyle = "#ccc";
    for (let i = 0; i <= 20; i++) {
        ctx.beginPath();
        ctx.moveTo(i * tileSize, 0);
        ctx.lineTo(i * tileSize, canvas.height);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, i * tileSize);
        ctx.lineTo(canvas.width, i * tileSize);
        ctx.stroke();
    }

    // Doel
    ctx.fillStyle = "black";
    ctx.fillRect(state.goal.x * tileSize, state.goal.y * tileSize, tileSize, tileSize);

    // Spelers
    for (const token in state.players) {
        const player = state.players[token];
        ctx.fillStyle = player.color;
        ctx.fillRect(player.x * tileSize, player.y * tileSize, tileSize, tileSize);
    }

    winnerElem.textContent = state.winner ? `🎉 Winnaar: ${state.winner}` : "Nog geen winnaar...";
}

// Server-Sent Events ontvangen
const evtSource = new EventSource('/stream');
evtSource.onmessage = (event) => {
    const state = JSON.parse(event.data);
    draw(state);
};
