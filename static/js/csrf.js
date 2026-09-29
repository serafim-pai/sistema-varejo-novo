// Adiciona o token de segurança (CSRF) em toda chamada fetch() que muda dados,
// para o navegador nunca precisar disso "na mão" nas telas do sistema.
(function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const token = meta ? meta.content : '';
    const PRECISA_TOKEN = ['POST', 'PUT', 'PATCH', 'DELETE'];
    const fetchOriginal = window.fetch;

    window.fetch = function (url, opcoes) {
        opcoes = opcoes || {};
        const metodo = (opcoes.method || 'GET').toUpperCase();
        if (PRECISA_TOKEN.includes(metodo)) {
            opcoes.headers = Object.assign({'X-CSRFToken': token}, opcoes.headers || {});
        }
        return fetchOriginal(url, opcoes);
    };
})();
