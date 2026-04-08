window.ONLYJOBS_STATE_META = window.ONLYJOBS_STATE_META || [];
window.ONLYJOBS_STATE_INDEX = window.ONLYJOBS_STATE_INDEX || {};

window.loadOnlyJobsStateMeta = function() {
  if (window.__onlyJobsStateMetaPromise) return window.__onlyJobsStateMetaPromise;

  window.__onlyJobsStateMetaPromise = fetch('state_portals.json')
    .then(function(response) { return response.json(); })
    .then(function(payload) {
      var states = payload && Array.isArray(payload.states) ? payload.states : [];
      var index = {};
      states.forEach(function(entry) {
        index[entry.name] = {
          name: entry.name,
          type: entry.type,
          portalUrl: entry.portal_url || '',
          aliases: entry.aliases || []
        };
      });
      window.ONLYJOBS_STATE_META = states;
      window.ONLYJOBS_STATE_INDEX = index;
      return states;
    })
    .catch(function() {
      window.ONLYJOBS_STATE_META = [];
      window.ONLYJOBS_STATE_INDEX = {};
      return [];
    });

  return window.__onlyJobsStateMetaPromise;
};
