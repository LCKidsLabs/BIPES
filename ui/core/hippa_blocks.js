// HippaFone blocks for BIPES.
// Block shapes first, then the Python each block writes. The generators call
// hippa.py, the board's helper module, which the HippaFone setup script
// (ui/hippafone/deploy_all_to_adafruit_ESP32-S3_Feather_5477.py) installs on the board.
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

  // ---- Screen, pictures, touch, keyboard, radio details, light, battery ----
  function numIn(name) { return {type: "input_value", name: name, check: "Number"}; }
  function colourIn(name, def) { return {type: "field_colour", name: name, colour: def}; }
  function colourCode(block, name) { return JSON.stringify(block.getFieldValue(name)); }
  function stmtGen(fn, parts) {
    // parts: list of [kind, name, default]; kind is 'v' (value input) or 'c' (colour field)
    return function(block) {
      imp();
      var a = parts.map(function(p) {
        return p[0] === 'c' ? colourCode(block, p[1]) : val(block, p[1], p[2]);
      });
      return 'hippa.' + fn + '(' + a.join(', ') + ')\n';
    };
  }

  stmt('hippa_screen_status', "set status line to %1", textIn(), "Changes the small line of words at the bottom of the screen.");
  stmt('hippa_screen_redraw', "redraw the screen", [], "Draws the title, the lines and the status line again, for example after a picture.");
  stmt('hippa_screen_rotate', "turn screen %1 degrees",
    [{type: "field_dropdown", name: "DEG", options: [["0", "0"], ["90", "90"], ["180", "180"], ["270", "270"]]}],
    "0 is the way the screen was installed; the other numbers turn it from there.");
  rep('hippa_screen_width', "screen width", [], "Number", "How many dots wide the screen is right now; it is 480 until you turn the screen sideways.");
  rep('hippa_screen_height', "screen height", [], "Number", "How many dots tall the screen is right now; it is 320 until you turn the screen sideways.");
  stmt('hippa_screen_box', "draw box x %1 y %2 width %3 height %4 colour %5",
    [numIn("X"), numIn("Y"), numIn("W"), numIn("H"), colourIn("COLOUR", "#ffffff")],
    "Draws a filled box; x and y count dots from the top left corner of the screen.");
  stmt('hippa_screen_text', "write %1 at x %2 y %3 colour %4 on %5",
    [{type: "input_value", name: "TEXT", check: "String"}, numIn("X"), numIn("Y"),
     colourIn("COLOUR", "#ffffff"), colourIn("BACKGROUND", "#000000")],
    "Writes your words anywhere on the screen, in the colours you pick; each letter is 12 dots wide and 24 dots tall.");
  stmt('hippa_picture_show', "show picture %1 in the middle", [{type: "input_value", name: "NAME", check: "String"}],
    "Shows a picture saved on the HippaFone or on its SD card in the middle of the screen; a moving picture keeps moving until you show another picture, clear the screen, or stop it.");
  stmt('hippa_picture_show_xy', "show picture %1 at x %2 y %3",
    [{type: "input_value", name: "NAME", check: "String"}, numIn("X"), numIn("Y")],
    "Shows a picture saved on the HippaFone or on its SD card with its top left corner at x and y dots from the top left of the screen.");
  stmt('hippa_picture_stop', "stop the moving picture", [], "Makes a moving picture stop moving.");
  rep('hippa_picture_list', "pictures on the SD card", [], "Array", "A list of the picture names on the SD card; the list is empty if there is no SD card.");
  rep('hippa_touch_tapped', "screen tapped?", [], "Boolean", "True once each time you tap the screen.");
  rep('hippa_touch_down', "finger on the screen?", [], "Boolean", "True the whole time a finger is touching the screen.");
  rep('hippa_touch_x', "touch x", [], "Number", "How many dots from the left of the screen you last touched; it is -1 until the first touch.");
  rep('hippa_touch_y', "touch y", [], "Number", "How many dots from the top of the screen you last touched; it is -1 until the first touch.");
  rep('hippa_battery_percent', "battery percent", [], "Number", "How full the battery is, from 0 to 100 percent.");
  rep('hippa_battery_volts', "battery volts", [], "Number", "The battery power in volts: about 3.2 when it is empty and 4.2 when it is full; it is -1 if the battery meter does not answer.");
  rep('hippa_typing', "words typed so far", [], "String", "The words you are typing right now, before you press Enter.");
  stmt('hippa_bluetooth_keyboard_on', "switch the Bluetooth keyboard on", [], "Lets a Bluetooth keyboard connect so you can type on the HippaFone.");
  rep('hippa_bluetooth_keyboard_ready', "Bluetooth keyboard connected?", [], "Boolean", "True when a Bluetooth keyboard is connected.");
  rep('hippa_radio_sender', "who sent the last message", [], "String", "The name of whoever sent the last radio message.");
  rep('hippa_radio_words', "words of the last message", [], "String", "The words of the last radio message.");
  rep('hippa_radio_rssi', "signal strength of the last message (dBm)", [], "Number", "How strong the last radio message was; 0 means no reading; signal readings need the PROTO radio mode.");
  rep('hippa_radio_snr', "signal clearness of the last message (dB)", [], "Number", "How clear the last radio message was; 0 means no reading; signal readings need the PROTO radio mode.");
  stmt('hippa_light_flash', "flash light %1 for %2 milliseconds", [colourIn("COLOUR", "#00ff00"), numIn("MS")],
    "Flashes the light in the colour you pick and then turns it off, while your program keeps going.");
  stmt('hippa_light_rgb', "light red %1 green %2 blue %3", [numIn("R"), numIn("G"), numIn("B")],
    "Turns the light on by mixing red, green and blue, each from 0 (none) to 255 (the most).");

  P['hippa_screen_status'] = call('screen_status', 'TEXT', "''");
  P['hippa_screen_redraw'] = call('screen_redraw');
  P['hippa_screen_rotate'] = function(block) {
    imp();
    return 'hippa.screen_rotate(' + block.getFieldValue('DEG') + ')\n';
  };
  P['hippa_screen_width'] = expr('hippa.screen_width()');
  P['hippa_screen_height'] = expr('hippa.screen_height()');
  P['hippa_screen_box'] = stmtGen('screen_box', [['v', 'X', '0'], ['v', 'Y', '0'], ['v', 'W', '0'], ['v', 'H', '0'], ['c', 'COLOUR']]);
  P['hippa_screen_text'] = stmtGen('screen_text', [['v', 'TEXT', "''"], ['v', 'X', '0'], ['v', 'Y', '0'], ['c', 'COLOUR'], ['c', 'BACKGROUND']]);
  P['hippa_picture_show'] = call('picture_show', 'NAME', "''");
  P['hippa_picture_show_xy'] = stmtGen('picture_show', [['v', 'NAME', "''"], ['v', 'X', '0'], ['v', 'Y', '0']]);
  P['hippa_picture_stop'] = call('picture_stop');
  P['hippa_picture_list'] = expr('hippa.picture_list()');
  P['hippa_touch_tapped'] = expr('hippa.touch_tapped()');
  P['hippa_touch_down'] = expr('hippa.touch_is_down()');
  P['hippa_touch_x'] = expr('hippa.touch_x()');
  P['hippa_touch_y'] = expr('hippa.touch_y()');
  P['hippa_battery_percent'] = expr('hippa.battery_percent()');
  P['hippa_battery_volts'] = expr('hippa.battery_volts()');
  P['hippa_typing'] = expr('hippa.typing()');
  P['hippa_bluetooth_keyboard_on'] = call('keyboard_bluetooth_on');
  P['hippa_bluetooth_keyboard_ready'] = expr('hippa.keyboard_bluetooth_connected()');
  P['hippa_radio_sender'] = expr('hippa.radio_sender()');
  P['hippa_radio_words'] = expr('hippa.radio_words()');
  P['hippa_radio_rssi'] = expr('hippa.radio_rssi()');
  P['hippa_radio_snr'] = expr('hippa.radio_snr()');
  P['hippa_light_flash'] = stmtGen('light_flash', [['c', 'COLOUR'], ['v', 'MS', '0']]);
  P['hippa_light_rgb'] = stmtGen('light', [['v', 'R', '0'], ['v', 'G', '0'], ['v', 'B', '0']]);
})();
