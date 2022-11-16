let socket = io("http://" + window.location.hostname + ":" + window.location.port);
let terminal_text = [];


socket.on("progress", function(message) {
    let timer = document.getElementById("timer");
    timer.innerHTML =
        "Time elapsed: None";

    let terminal = document.getElementById("console");
    terminal_text.push(message["stdout"])
    terminal.innerHTML = terminal_text.join("");
});


socket.on("delete_row", function() {
    terminal_text.pop();
});


socket.on("download", function(paths) {
    paths.forEach(function (path, index) {
        let a = document.createElement("a");
        a.href = path;
        a.download = path.split("/").pop();
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });
});


form.addEventListener("submit", (e) => {
    e.preventDefault();

    let dict = {}
    const formData = new FormData(document.querySelector("form"))
    for (let pair of formData.entries()) {
        dict[pair[0]] = pair[1];
    }
    socket.emit("send", dict)
});
