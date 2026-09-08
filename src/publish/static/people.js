/* Find a councillor.
 *
 * Progressive enhancement, and nothing else. The page is complete without this
 * file: every councillor is already rendered, grouped by ward, with a jump list
 * above them. This adds a search box and a party filter for people who would
 * rather type than scroll, and it builds its own controls, so if the script
 * never loads nothing on the page refers to something that is not there.
 *
 * It sorts and filters. It does not rank, count into an order, or score. */
(function () {
  "use strict";
  var host = document.getElementById("people-controls");
  var list = document.getElementById("people-list");
  var empty = document.getElementById("people-empty");
  if (!host || !list) return;

  var cards = Array.prototype.slice.call(list.querySelectorAll(".pcard"));
  if (cards.length < 8) return;
  var wards = Array.prototype.slice.call(list.querySelectorAll(".pward"));
  var parties = [];
  cards.forEach(function (c) {
    var p = c.getAttribute("data-party");
    if (p && parties.indexOf(p) === -1) parties.push(p);
  });
  parties.sort();

  host.innerHTML =
    '<div class="pcontrol">' +
    '<label for="people-q">Search by name or ward</label>' +
    '<input id="people-q" type="search" autocomplete="off" placeholder="Bowthorpe, or Lawes">' +
    "</div>" +
    '<div class="pcontrol">' +
    '<label for="people-party">Party</label>' +
    '<select id="people-party"><option value="">Every party</option>' +
    parties.map(function (p) {
      return '<option value="' + p.replace(/"/g, "&quot;") + '">' + p + "</option>";
    }).join("") +
    "</select></div>" +
    '<p class="pcontrol-count" id="people-count" role="status"></p>';
  host.hidden = false;

  var q = document.getElementById("people-q");
  var party = document.getElementById("people-party");
  var count = document.getElementById("people-count");

  function apply() {
    var text = q.value.trim().toLowerCase();
    var want = party.value;
    var shown = 0;
    cards.forEach(function (c) {
      var hit =
        (!text ||
          c.getAttribute("data-name").indexOf(text) !== -1 ||
          c.getAttribute("data-ward").indexOf(text) !== -1) &&
        (!want || c.getAttribute("data-party") === want);
      c.hidden = !hit;
      if (hit) shown++;
    });
    /* A ward with nothing left in it should not leave its heading behind. */
    wards.forEach(function (w) {
      var any = w.querySelector(".pcard:not([hidden])");
      w.hidden = !any;
    });
    if (empty) empty.hidden = shown !== 0;
    count.textContent =
      text || want
        ? shown + (shown === 1 ? " councillor" : " councillors") + " match."
        : "";
  }

  q.addEventListener("input", apply);
  party.addEventListener("change", apply);
})();
