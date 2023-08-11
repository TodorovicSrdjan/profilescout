from dataclasses import dataclass, field

from profilescout.common.constants import ConstantsNamespace
from profilescout.common.interfaces import DetectionStrategy
from profilescout.link.utils import most_common_format


constants = ConstantsNamespace


@dataclass
class OriginPageDetectionStrategy(DetectionStrategy):
    succeeded: bool = False
    result: dict = None
    origin_candidates: dict = field(default_factory=dict)

    def successful(self):
        return self.succeeded

    def get_result(self):
        return self.result

    def reset(self):
        self.succeeded = False
        self.result = None
        self.origin_candidates = dict()  # TODO determine whether or not this should be completely cleared

    def analyse(self, curr_page, classifier, resolution):
        action_result = curr_page.is_profile(classifier, *resolution)
        profile_detected = action_result.val
        if action_result.successful and profile_detected:
            # assume that this is initial page
            origin = curr_page.link.url
            parent_url = curr_page.link.parent_url
            if parent_url is not None:
                origin = parent_url
            if origin not in self.origin_candidates:
                self.origin_candidates[origin] = [curr_page.link.url]
            else:
                self.origin_candidates[origin] += [curr_page.link.url]

            # check if the profile page origin is found
            children = self.origin_candidates[origin]
            children_count = len(children)
            if children_count == constants.ORIGIN_PAGE_THRESHOLD:
                self.result = {
                    'origin': origin,
                    'depth': curr_page.link.depth - 1,
                    'most_common_format': most_common_format(children),  # TODO add placeholder
                    'message': f'Found profile page origin at {origin!r}'}
                self.succeeded = True
        return self.result
