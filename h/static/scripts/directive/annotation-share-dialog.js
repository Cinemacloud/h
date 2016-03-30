'use strict';

module.exports = function () {
  return {
    bindToController: true,
    controllerAs: 'vm',
    restrict: 'E',
    template: require('../../../templates/client/annotation_share_dialog.html'),
    controller: ['$timeout', '$scope', function ($timeout, $scope) {
      this.copyToClipboard = function(event) {
        var $container = angular.element(event.currentTarget).parent();
        var shareLinkInput = $container.find('input')[0];

        $scope.showCopyToClipboardMessage = true;

        try {
          shareLinkInput.select();
          document.execCommand('copy');

          $scope.copyToClipboardMessage = 'Link copied to clipboard!';
          $scope.copyToClipboardMessageClass = 'annotation-share-dialog-link--success';
        } catch (ex) {
          $scope.copyToClipboardMessage = 'Failed to copy link copied to clipboard!';
          $scope.copyToClipboardMessageClass = 'annotation-share-dialog-link--fail';
        } finally {
          setTimeout(function() {
              $scope.showCopyToClipboardMessage = false;
              $scope.$digest();
            },
            1000);
        }
      };
    }],
    scope: {
      group: '<',
      uri: '<',
      isPrivate: '<'
    }
  };
};
