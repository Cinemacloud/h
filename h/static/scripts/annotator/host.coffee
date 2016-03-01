queryString = require('query-string')
Annotator = require('annotator')
$ = Annotator.$

Guest = require('./guest')

module.exports = class Host extends Guest
  constructor: (element, options) ->
    args = {}

    if options.firstRun
      args['firstrun'] = true
    if options.liveReloadServer
      args['livereloadserver'] = options.liveReloadServer

    argString = queryString.stringify(args)
    if argString
      options.app += (if '?' in options.app then '&' else '?') + argString

    # Create the iframe
    app = $('<iframe></iframe>')
    .attr('name', 'hyp_sidebar_frame')
    # enable media in annotations to be shown fullscreen
    .attr('allowfullscreen', '')
    .attr('seamless', '')
    .attr('src', options.app)

    @frame = $('<div></div>')
    .css('display', 'none')
    .addClass('annotator-frame annotator-outer')
    .appendTo(element)

    super

    app.appendTo(@frame)

    this.on 'panelReady', =>
      # Initialize tool state.
      if options.showHighlights == undefined
        # Highlights are on by default.
        options.showHighlights = true
      this.setVisibleHighlights(options.showHighlights)

      # Show the UI
      @frame.css('display', '')

  destroy: ->
    @frame.remove()
    super
