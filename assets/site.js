// Só conveniências: o site funciona inteiro sem JavaScript.
(function () {
  var botao = document.querySelector(".menu-botao");
  var menu = document.getElementById("menu");
  if (botao && menu) {
    var fechar = function () {
      menu.classList.remove("aberto");
      botao.setAttribute("aria-expanded", "false");
    };
    botao.addEventListener("click", function () {
      var aberto = menu.classList.toggle("aberto");
      botao.setAttribute("aria-expanded", String(aberto));
    });
    menu.addEventListener("click", function (e) {
      if (e.target.tagName === "A") fechar();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") fechar();
    });
  }

  var links = Array.prototype.slice.call(document.querySelectorAll("#menu a[href^='#']"));
  if ("IntersectionObserver" in window && links.length) {
    var mapa = {};
    links.forEach(function (a) { mapa[a.getAttribute("href").slice(1)] = a; });
    var obs = new IntersectionObserver(function (itens) {
      itens.forEach(function (i) {
        if (i.isIntersecting && mapa[i.target.id]) {
          links.forEach(function (a) { a.removeAttribute("aria-current"); });
          mapa[i.target.id].setAttribute("aria-current", "true");
        }
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    Object.keys(mapa).forEach(function (id) {
      var s = document.getElementById(id);
      if (s) obs.observe(s);
    });
  }
})();
