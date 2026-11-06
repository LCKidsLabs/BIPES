// HippaFone blocks for BIPES. Pasted from the HippaFone guide.
// Block shapes first, then the Python each block writes.
(function() {
  var HUE = 290;
  var P = Blockly.Python;

  function stmt(name, msg, args, tip) {
    Blockly.Blocks[name] = { init: function() {
      this.jsonInit({message0: msg, args0: args, previousStatement: null,
        nextStatement: null, colour: HUE, tooltip: tip});
    } };
  }
  function rep(name, msg, args, out, tip) {
    Blockly.Blocks[name] = { init: function() {
      this.jsonInit({message0: msg, args0: args, output: out,
        colour: HUE, tooltip: tip});
    } };
  }
  function imp() { P.definitions_['import_hippa'] = 'import hippa'; }
  function val(block, n, d) { return P.valueToCode(block, n, P.ORDER_NONE) || d; }
  function textIn() { return [{type: "input_value", name: "TEXT", check: "String"}]; }

  stmt('hippa_screen_title', "set screen title to %1", textIn(), "Changes the big title at the top of the screen.");
  stmt('hippa_screen_write', "write %1 on screen", textIn(), "Shows your words on the screen.");
  stmt('hippa_screen_clear', "clear screen", [], "Wipes the screen clean.");
  stmt('hippa_radio_send', "send %1 to radio", textIn(), "Sends your words through the air to the other HippaFone.");
  stmt('hippa_light', "light %1", [{type: "field_colour", name: "COLOUR", colour: "#ff0000"}], "Turns the light on in the colour you pick.");
  stmt('hippa_light_off', "light off", [], "Turns the light off.");
  stmt('hippa_wait', "wait %1 seconds", [{type: "input_value", name: "SECONDS", check: "Number"}], "Pauses for a few seconds.");
  rep('hippa_radio_message', "new radio message", [], "String", "The words that just arrived by radio. Empty if nothing came.");
  rep('hippa_button_pressed', "BOOT button pressed?", [], "Boolean", "True once each time you press the BOOT button.");
  rep('hippa_button_down', "BOOT button held down?", [], "Boolean", "True the whole time the BOOT button is held down.");
  rep('hippa_typed_line', "line typed on the computer", [], "String", "The last line you typed on the computer.");
  rep('hippa_now', "seconds now", [], "Number", "How many seconds the HippaFone has been on.");

  Blockly.Blocks['hippa_forever'] = { init: function() {
    this.jsonInit({message0: "forever %1 %2",
      args0: [{type: "input_dummy"}, {type: "input_statement", name: "DO"}],
      previousStatement: null, nextStatement: null, colour: HUE,
      tooltip: "Does the blocks inside again and again, with no end."});
  } };

  function call(fn, input, d) {
    return function(block) {
      imp();
      return 'hippa.' + fn + '(' + (input ? val(block, input, d) : '') + ')\n';
    };
  }
  function expr(code) {
    return function(block) { imp(); return [code, P.ORDER_FUNCTION_CALL]; };
  }
  P['hippa_screen_title'] = call('screen_title', 'TEXT', "''");
  P['hippa_screen_write'] = call('screen_write', 'TEXT', "''");
  P['hippa_screen_clear'] = call('screen_clear');
  P['hippa_radio_send'] = call('radio_send', 'TEXT', "''");
  P['hippa_light_off'] = call('light_off');
  P['hippa_wait'] = call('wait', 'SECONDS', '0');
  P['hippa_light'] = function(block) {
    imp();
    return 'hippa.light(' + JSON.stringify(block.getFieldValue('COLOUR')) + ')\n';
  };
  P['hippa_radio_message'] = expr('hippa.radio_message()');
  P['hippa_typed_line'] = expr('hippa.typed_line()');
  P['hippa_now'] = expr('hippa.now()');
  P['hippa_button_pressed'] = expr('hippa.button_pressed()');
  P['hippa_button_down'] = expr('hippa.button_is_down()');
  P['hippa_forever'] = function(block) {
    imp();
    return 'while True:\n' + (P.statementToCode(block, 'DO') || P.PASS);
  };
})();
